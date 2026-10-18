"""Mutation engine: inject named flaws into clean notebooks, with proof.

Every mutation must mechanically verify that the flaw is really present in
the mutant (execution fingerprint or AST fact). A mutant without proof
never enters the corpus — otherwise the whole eval stands on sand.

One mutation per notebook (isolation of measurement). Cell indices in the
notebook's waldean metadata refer to the clean base; mutations either edit
in place or insert cells and never rely on post-insertion indices.
"""

from __future__ import annotations

import copy
import random
import re

import libcst as cst
import nbformat

from ..runtime import execute as ex
from ..analysis.dataflow import analyze
from ..checks.detect import CORRECTION_RE, LOOP_TEST_WEIGHT, MULTIPLE_TESTING_THRESHOLD, TEST_FUNCS
from ..analysis.ingest import from_nbnode


def meta(nb_node) -> dict:
    return dict(nb_node.metadata.get("waldean", {}))


def _cell_stmts(source: str) -> tuple[cst.Module, list]:
    module = cst.parse_module(source)
    return module, list(module.body)


def _stmt_code(module: cst.Module, stmt) -> str:
    return module.code_for_node(stmt)


def _replace_cell(nb_node, index: int, new_source: str):
    nb = copy.deepcopy(nb_node)
    nb.cells[index]["source"] = new_source
    nb.cells[index]["outputs"] = []
    nb.cells[index]["execution_count"] = None
    return nb


def _insert_code_cell(nb_node, index: int, source: str):
    nb = copy.deepcopy(nb_node)
    nb.cells.insert(index, nbformat.v4.new_code_cell(source))
    return nb


def _replace_markdown(nb_node, index: int, text: str):
    nb = copy.deepcopy(nb_node)
    nb.cells[index]["source"] = text
    return nb


# phrasing variants 0-1 are dev-only; 2-4 exist only in held-out mutants,
# and variant 4 is a rhetorical shape (question-then-answer) never seen in
# dev — memorizing dev phrasings cannot cover it (risk R3)
DEV_VARIANTS = (0, 1)
HELDOUT_VARIANTS = (2, 3, 4)


def phrasing_variant(seed: int, base_seed: int) -> int:
    pool = DEV_VARIANTS if seed < 2 else HELDOUT_VARIANTS
    return pool[(seed + base_seed) % len(pool)]


class Mutation:
    flaw_id: str = ""
    POOL: tuple[str, ...] = ()

    def applicable(self, nb_node) -> bool:
        raise NotImplementedError

    def apply(self, nb_node, seed: int):
        raise NotImplementedError

    def verify(self, mutated_node) -> tuple[bool, dict]:
        raise NotImplementedError

    def conclusion(self, nb_node, seed: int) -> str | None:
        if not self.POOL:
            return None
        return self.POOL[phrasing_variant(seed, meta(nb_node)["seed"])]


class FitBeforeSplitMutation(Mutation):
    """Move the scaler fit before train_test_split, consuming the full frame."""

    flaw_id = "leakage-fit-before-split"

    def applicable(self, nb_node) -> bool:
        m = meta(nb_node)
        if "split_cell" not in m:
            return False
        src = nb_node.cells[m["split_cell"]]["source"]
        return "train_test_split" in src and "fit_transform" in src

    def apply(self, nb_node, seed: int):
        m = meta(nb_node)
        idx = m["split_cell"]
        module, stmts = _cell_stmts(nb_node.cells[idx]["source"])

        split_stmt = fit_stmt = transform_stmt = scaler_def = None
        for s in stmts:
            code = _stmt_code(module, s)
            if "train_test_split" in code:
                split_stmt = s
            elif ".fit_transform(" in code:
                fit_stmt = s
            elif ".transform(" in code:
                transform_stmt = s
            elif "StandardScaler()" in code:
                scaler_def = s
        if not all([split_stmt, fit_stmt, transform_stmt, scaler_def]):
            raise ValueError("canonical split cell not found")

        split_code = _stmt_code(module, split_stmt)
        call_args = re.search(r"train_test_split\(\s*(\w+)\s*,", split_code)
        if call_args is None:
            raise ValueError("canonical split cell not found")
        pre_name = call_args.group(1)
        rest = [s for s in stmts if s not in {split_stmt, fit_stmt, transform_stmt, scaler_def}]
        if seed % 2 == 1:
            hand = cst.parse_statement(
                f"{pre_name} = ({pre_name} - {pre_name}.mean()) / {pre_name}.std()\n"
            )
            new_body = [hand, split_stmt] + rest
        else:
            new_fit = cst.parse_statement(f"{pre_name} = scaler.fit_transform({pre_name})\n")
            new_body = [scaler_def, new_fit, split_stmt] + rest
        new_source = module.with_changes(body=new_body).code.rstrip("\n")
        return _replace_cell(nb_node, idx, new_source)

    def verify(self, mutated_node) -> tuple[bool, dict]:
        m = meta(mutated_node)
        src = mutated_node.cells[m["split_cell"]]["source"]
        if "scaler.fit_transform" in src:
            probe = (
                "print('WALDEAN_VERIFY_LEAK', int(getattr(scaler, 'n_samples_seen_', -1)), int(len(y)))"
            )
        else:
            call_args = re.search(r"train_test_split\(\s*(\w+)\s*,", src)
            if call_args is None:
                return False, {"reason": "train_test_split not found in split_cell"}
            pre_name = call_args.group(1)
            probe = (
                f"_m = np.asarray({pre_name}, dtype=float)\n"
                f"print('WALDEAN_VERIFY_LEAK', int(len(_m)) if "
                f"np.abs(_m.mean(axis=0)).max() < 1e-9 and np.abs(_m.std(axis=0, ddof=1) - 1).max() < 1e-9 "
                f"else -1, int(len(y)))"
            )
        executed = ex.execute(ex.with_appended_code_cell(mutated_node, probe))
        lines = ex.stdout_lines(executed, "WALDEAN_VERIFY_LEAK")
        if not lines:
            return False, {"reason": "no verify output"}
        _, seen, total = lines[-1].split()
        ok = int(seen) == int(total) and int(seen) > 0
        return ok, {"rows_in_statistic": int(seen), "total_rows": int(total)}


class MultipleTestingMutation(Mutation):
    """Insert an uncorrected t-test screen over many columns, plus a
    conclusion that cites the 'significant' hits."""

    flaw_id = "testing-multiple-uncorrected"

    def applicable(self, nb_node) -> bool:
        m = meta(nb_node)
        return bool(m.get("num_cols")) and bool(m.get("binary_col") or m.get("target_col"))

    def apply(self, nb_node, seed: int):
        m = meta(nb_node)
        rng = random.Random(seed)
        cols = list(m["num_cols"])
        k = min(len(cols), 8)
        tested = rng.sample(cols, k)

        if m.get("binary_col"):
            col, v1, v0 = m["binary_col"], m["binary_values"][0], m["binary_values"][1]
            a = f"df[df[{col!r}] == {v1!r}][c]"
            b = f"df[df[{col!r}] == {v0!r}][c]"
        else:
            t = m["target_col"]
            a = f"df[df[{t!r}] > df[{t!r}].median()][c]"
            b = f"df[df[{t!r}] <= df[{t!r}].median()][c]"

        code = (
            "from scipy.stats import ttest_ind\n"
            f"cols_to_test = {tested!r}\n"
            "significant = []\n"
            "for c in cols_to_test:\n"
            f"    stat, p = ttest_ind({a}, {b})\n"
            "    if p < 0.05:\n"
            "        significant.append(c)\n"
            "print('tested', len(cols_to_test), 'columns; significant:', significant)"
        )
        md = (
            "Screening all available metrics, we identified the significant "
            "drivers listed above — these differ reliably between groups and "
            "should be prioritized."
        )
        idx = m["conclusion_cell"]
        nb = _insert_code_cell(nb_node, idx, code)
        nb.cells.insert(idx + 1, nbformat.v4.new_markdown_cell(md))
        return nb

    def verify(self, mutated_node) -> tuple[bool, dict]:
        nb = from_nbnode(mutated_node)
        flow = analyze(nb)
        sites = [c for c in flow.calls if c.name in TEST_FUNCS]
        effective_n = sum(LOOP_TEST_WEIGHT if c.loop_depth > 0 else 1 for c in sites)
        corrected = bool(CORRECTION_RE.search(nb.full_source()))
        ok = effective_n > MULTIPLE_TESTING_THRESHOLD and not corrected
        if ok:  # must also actually run
            ex.execute(mutated_node)
        return ok, {"effective_tests": effective_n, "correction_present": corrected}


class _DropImportNames(cst.CSTTransformer):
    def __init__(self, names: set[str]):
        self.names = names

    def leave_ImportFrom(self, original_node, updated_node):
        if isinstance(updated_node.names, cst.ImportStar):
            return updated_node
        kept = [a for a in updated_node.names if a.name.value not in self.names]
        if not kept:
            return cst.RemoveFromParent()
        kept[-1] = kept[-1].with_changes(comma=cst.MaybeSentinel.DEFAULT)
        return updated_node.with_changes(names=kept)


class BaserateAccuracyMutation(Mutation):
    """Strip AUC, keep accuracy as the only metric, rewrite the conclusion
    to an accuracy brag with no imbalance mention."""

    flaw_id = "baserate-accuracy-imbalanced"

    def applicable(self, nb_node) -> bool:
        m = meta(nb_node)
        return bool(m.get("imbalanced")) and "metrics_cell" in m and "imports_cell" in m

    def apply(self, nb_node, seed: int):
        m = meta(nb_node)
        # 1) metrics cell: drop auc/proba lines, accuracy-only print
        idx = m["metrics_cell"]
        module, stmts = _cell_stmts(nb_node.cells[idx]["source"])
        new_body = []
        for s in stmts:
            code = _stmt_code(module, s)
            if "roc_auc" in code or "predict_proba" in code:
                continue
            if code.strip().startswith("print("):
                s = cst.parse_statement('print(f"accuracy={acc:.3f}")\n')
            new_body.append(s)
        nb = _replace_cell(nb_node, idx, module.with_changes(body=new_body).code.rstrip("\n"))

        # 2) imports cell: remove roc_auc_score so no metric token survives
        imp_idx = m["imports_cell"]
        imp_module = cst.parse_module(nb.cells[imp_idx]["source"])
        new_imports = imp_module.visit(_DropImportNames({"roc_auc_score"}))
        nb = _replace_cell(nb, imp_idx, new_imports.code.rstrip("\n"))

        # 3) conclusion: accuracy overclaim, imbalance mention gone
        md = (
            "The classifier is highly accurate on held-out data — "
            "performance is strong and the model is ready to use."
        )
        return _replace_markdown(nb, m["conclusion_cell"], md)

    def verify(self, mutated_node) -> tuple[bool, dict]:
        src = "\n".join(
            c["source"] for c in mutated_node.cells if c["cell_type"] == "code"
        )
        if "roc_auc" in src:
            return False, {"reason": "auc still present"}
        probe = (
            "import pandas as _pd\n"
            "_maj = float(_pd.Series(y_te).value_counts(normalize=True).max())\n"
            "print('WALDEAN_VERIFY_BASERATE', _maj, float(acc))"
        )
        executed = ex.execute(ex.with_appended_code_cell(mutated_node, probe))
        lines = ex.stdout_lines(executed, "WALDEAN_VERIFY_BASERATE")
        if not lines:
            return False, {"reason": "no verify output"}
        _, maj, acc = lines[-1].split()
        ok = float(maj) >= float(acc) - 0.02
        return ok, {"majority_baseline": float(maj), "reported_accuracy": float(acc)}


POPULATION_RE = re.compile(
    r"\ball\b|\bentire\b|\bwhole\b|\bevery\b|population|customer value|customer base",
    re.IGNORECASE,
)
SCOPING_RE = re.compile(r"active|retained|surviv|complet", re.IGNORECASE)


class SurvivorshipMutation(Mutation):
    """Filter the cohort to survivors, then state the conclusion about the
    whole population."""

    flaw_id = "selection-survivorship-cohort"

    FILTERS = (
        'df = df[df["status"] == "active"]',
        "df = df.query(\"status == 'active'\")",
    )
    POOL = (
        "Average customer LTV grows steadily across signup cohorts — the "
        "product increases customer value over time.",
        "LTV per cohort keeps climbing quarter over quarter: every new "
        "cohort of customers is worth more than the last.",
        "The upward trend in cohort lifetime value means our customer base "
        "as a whole is becoming more valuable.",
        "Each successive signup quarter delivers higher average LTV, so "
        "the business now extracts more value from all its customers.",
        "Is customer value improving? The cohort table answers clearly: "
        "across the entire customer population, later signups are worth "
        "more.",
    )

    def applicable(self, nb_node) -> bool:
        m = meta(nb_node)
        return m.get("status_col") == "status" and "agg_cell" in m and "conclusion_cell" in m

    def apply(self, nb_node, seed: int):
        m = meta(nb_node)
        filter_line = self.FILTERS[seed % 2]
        if seed % 2 == 0:
            idx = m["agg_cell"]
            nb = _replace_cell(nb_node, idx, filter_line + "\n" + nb_node.cells[idx]["source"])
        else:
            nb = _insert_code_cell(nb_node, m["agg_cell"], filter_line)
        # conclusion index unshifted with the prepended filter; +1 after insert
        concl = m["conclusion_cell"] + (0 if seed % 2 == 0 else 1)
        text = self.conclusion(nb_node, seed)
        if text is None:
            raise ValueError("empty conclusion pool")
        return _replace_markdown(nb, concl, text)

    def verify(self, mutated_node) -> tuple[bool, dict]:
        src = "\n".join(
            c["source"] for c in mutated_node.cells if c["cell_type"] == "code"
        )
        if not any(f in src for f in self.FILTERS):
            return False, {"reason": "filter missing"}
        md = "\n".join(
            c["source"] for c in mutated_node.cells if c["cell_type"] == "markdown"
        )
        population_claim = bool(POPULATION_RE.search(md))
        scoped = bool(SCOPING_RE.search(md))
        ok = population_claim and not scoped
        if ok:
            ex.execute(mutated_node)
        return ok, {"population_claim": population_claim, "scoped_language": scoped}


EFFECT_SIZE_RE = re.compile(
    r"effect[ -]size|cohen|confidence interval|\bci\b|\bd\s*=", re.IGNORECASE
)
RECOMMEND_RE = re.compile(
    r"\b(roll|ship|launch|recommend|adopt|deploy)", re.IGNORECASE
)


class SignificanceMeaninglessMutation(Mutation):
    """Blow the sample up so a ~0.04 SD effect is p<0.05 near-certain; the
    Cohen's d computation stays in code — the flaw is the prose citing only
    p and recommending rollout."""

    flaw_id = "significance-meaningless"

    POOL = (
        "The checkout redesign produced a statistically significant "
        "improvement in session time (p < 0.05). We recommend rolling "
        "variant B out to all users.",
        "Variant B beat A on the primary metric with p < 0.05. The result "
        "is statistically significant, so B should be shipped to 100% of "
        "traffic.",
        "With the p-value comfortably below the 0.05 threshold, the "
        "experiment is decisive: launch the new checkout for the entire "
        "user base.",
        "Our significance test cleared the bar (p < 0.05), which settles "
        "it — the data supports adopting variant B as the default "
        "experience going forward.",
        "Did the redesign work? The statistics say yes: p < 0.05 on the "
        "primary metric. Roll variant B out to everyone.",
    )

    def applicable(self, nb_node) -> bool:
        m = meta(nb_node)
        if "datagen_cell" not in m or "conclusion_cell" not in m:
            return False
        src = nb_node.cells[m["datagen_cell"]]["source"]
        return "session_minutes" in src and "n = 2400" in src

    def apply(self, nb_node, seed: int):
        m = meta(nb_node)
        idx = m["datagen_cell"]
        # 20k/group and a 0.17-minute lift: ~0.045 SD (gamma(3, 2.2) has
        # sd 3.81), z ~ 4.5, so p<0.05 holds for essentially every seed
        src = nb_node.cells[idx]["source"]
        src = src.replace("n = 2400", "n = 40000")
        src = src.replace('(variant == "B") * 0.5', '(variant == "B") * 0.17')
        nb = _replace_cell(nb_node, idx, src)
        text = self.conclusion(nb_node, seed)
        if text is None:
            raise ValueError("empty conclusion pool")
        return _replace_markdown(nb, m["conclusion_cell"], text)

    def verify(self, mutated_node) -> tuple[bool, dict]:
        probe = "print('WALDEAN_VERIFY_SIG', float(p), float(d))"
        executed = ex.execute(ex.with_appended_code_cell(mutated_node, probe))
        lines = ex.stdout_lines(executed, "WALDEAN_VERIFY_SIG")
        if not lines:
            return False, {"reason": "no verify output"}
        _, p, d = lines[-1].split()
        md = "\n".join(
            c["source"] for c in mutated_node.cells if c["cell_type"] == "markdown"
        )
        effect_mentioned = bool(EFFECT_SIZE_RE.search(md))
        recommends = bool(RECOMMEND_RE.search(md))
        ok = float(p) < 0.05 and abs(float(d)) < 0.2 and not effect_mentioned and recommends
        return ok, {
            "p": float(p), "cohens_d": float(d),
            "effect_size_in_markdown": effect_mentioned, "recommendation": recommends,
        }


CAUSAL_RE = re.compile(r"caused|effect of|drove|produced|worked", re.IGNORECASE)
CONTROL_RE = re.compile(r"control|comparison group|untreated", re.IGNORECASE)
EXTREME_SELECTORS = {"nsmallest", "nlargest", "quantile"}


class RegressionToMeanMutation(Mutation):
    """Select an extreme group at period 1 and read its period-2 move toward
    the mean as the effect of a program, with no control group."""

    flaw_id = "regression-to-mean-claim"

    POOL = (
        "Accounts flagged for unusual spend were enrolled in the "
        "spend-stabilization program, and their spend moved back toward "
        "typical levels the next quarter. The program clearly worked — the "
        "intervention caused the correction.",
        "After we enrolled the most extreme spenders in the stabilization "
        "initiative, their quarterly spend normalized. That shift is the "
        "direct effect of the initiative.",
        "The outreach paid off: accounts singled out for atypical spending "
        "returned to ordinary levels once the program took hold, which "
        "shows the program drove the turnaround.",
        "Enrollment in the outreach scheme produced a marked normalization "
        "in the flagged accounts' spending — proof that the scheme changed "
        "spending behavior.",
        "Did the stabilization program work? The numbers say yes — flagged "
        "accounts' spend moved back to normal in the following quarter, a "
        "change the program caused.",
    )

    def applicable(self, nb_node) -> bool:
        m = meta(nb_node)
        return "period_cols" in m and "conclusion_cell" in m

    def apply(self, nb_node, seed: int):
        m = meta(nb_node)
        p1, p2 = m["period_cols"]
        select = [
            f"flagged = df.nsmallest(150, {p1!r})",
            f"flagged = df.nlargest(150, {p1!r})",
            f"flagged = df[df[{p1!r}] <= df[{p1!r}].quantile(0.05)]",
        ][seed % 3]
        code = (
            select + "\n"
            'print("flagged", len(flagged),\n'
            f'      "q1", round(flagged[{p1!r}].mean(), 2),\n'
            f'      "q2", round(flagged[{p2!r}].mean(), 2))'
        )
        idx = m["conclusion_cell"]
        nb = _insert_code_cell(nb_node, idx, code)
        text = self.conclusion(nb_node, seed)
        if text is None:
            raise ValueError("empty conclusion pool")
        nb.cells.insert(idx + 1, nbformat.v4.new_markdown_cell(text))
        return nb

    def verify(self, mutated_node) -> tuple[bool, dict]:
        nb = from_nbnode(mutated_node)
        flow = analyze(nb)
        selections = [c for c in flow.calls if c.name in EXTREME_SELECTORS]
        if len(selections) != 1 or CONTROL_RE.search(nb.full_source()):
            return False, {"reason": "selection/control structure wrong",
                           "selection_calls": len(selections)}
        p1, p2 = meta(mutated_node)["period_cols"]
        probe = (
            f"print('WALDEAN_VERIFY_RTM', float(flagged[{p1!r}].mean()), "
            f"float(flagged[{p2!r}].mean()), float(df[{p1!r}].mean()), "
            f"float(df[{p2!r}].mean()))"
        )
        executed = ex.execute(ex.with_appended_code_cell(mutated_node, probe))
        lines = ex.stdout_lines(executed, "WALDEAN_VERIFY_RTM")
        if not lines:
            return False, {"reason": "no verify output"}
        _, s1, s2, g1, g2 = lines[-1].split()
        moved = abs(float(s2) - float(g2)) < abs(float(s1) - float(g1))
        md = "\n".join(
            c["source"] for c in mutated_node.cells if c["cell_type"] == "markdown"
        )
        causal = bool(CAUSAL_RE.search(md))
        control_lang = bool(CONTROL_RE.search(md))
        ok = moved and causal and not control_lang
        return ok, {
            "selected_q1_mean": float(s1), "selected_q2_mean": float(s2),
            "grand_q1_mean": float(g1), "grand_q2_mean": float(g2),
            "causal_claim": causal, "control_language": control_lang,
        }


class TemporalShuffleMutation(Mutation):
    """Break temporal ordering: either randomize the train/test split or
    swap the walk-forward CV splitter for a shuffled KFold."""

    flaw_id = "leakage-temporal-shuffle"

    CONCLUSION = (
        "The model reaches the MAE and R^2 printed above on the held-out "
        "split, with cross-validated MAE shown alongside."
    )

    def applicable(self, nb_node) -> bool:
        m = meta(nb_node)
        return "temporal_split_cell" in m and "temporal_cv_cell" in m and "date_col" in m

    def apply(self, nb_node, seed: int):
        m = meta(nb_node)
        variant = seed % 2
        if variant == 0:
            idx = m["temporal_split_cell"]
            src = nb_node.cells[idx]["source"]
            if "shuffle=False" not in src:
                raise ValueError("shuffle=False not found in temporal_split_cell")
            new_src = src.replace("shuffle=False", f"random_state={40 + seed}")
        else:
            idx = m["temporal_cv_cell"]
            src = nb_node.cells[idx]["source"]
            if "cv = TimeSeriesSplit(n_splits=5)" not in src:
                raise ValueError("cv = TimeSeriesSplit(n_splits=5) not found in temporal_cv_cell")
            new_src = src.replace(
                "cv = TimeSeriesSplit(n_splits=5)",
                "from sklearn.model_selection import KFold\n"
                f"cv = KFold(n_splits=5, shuffle=True, random_state={seed})",
            )
        nb = _replace_cell(nb_node, idx, new_src)
        return _replace_markdown(nb, m["conclusion_cell"], self.CONCLUSION)

    def verify(self, mutated_node) -> tuple[bool, dict]:
        m = meta(mutated_node)
        cv_src = mutated_node.cells[m["temporal_cv_cell"]]["source"]
        variant = 1 if "KFold" in cv_src else 0

        nb = from_nbnode(mutated_node)
        flow = analyze(nb)
        if variant == 0:
            tts_calls = [c for c in flow.calls if c.name == "train_test_split"]
            if any(c.kw_args.get("shuffle") == {"False"} for c in tts_calls):
                return False, {"reason": "shuffle=False still present on train_test_split"}
        else:
            if any(c.name == "TimeSeriesSplit" for c in flow.calls):
                return False, {"reason": "TimeSeriesSplit call still present"}

        if variant == 0:
            probe = (
                "_trd = df.loc[X_tr.index, 'date']\n"
                "_ted = df.loc[X_te.index, 'date']\n"
                "print('WALDEAN_VERIFY_TEMPORAL', int(_trd.max() > _ted.min()), "
                "_trd.max().date(), _ted.min().date())"
            )
            executed = ex.execute(ex.with_appended_code_cell(mutated_node, probe))
            lines = ex.stdout_lines(executed, "WALDEAN_VERIFY_TEMPORAL")
            if not lines:
                return False, {"reason": "no verify output"}
            _, flag, train_max, test_min = lines[-1].split()
            ok = int(flag) == 1
            return ok, {"variant": 0, "train_max_date": train_max, "test_min_date": test_min}
        else:
            probe = (
                "_tr, _te = next(iter(cv.split(X)))\n"
                "print('WALDEAN_VERIFY_TEMPORAL_CV', "
                "int(df['date'].iloc[_tr].max() > df['date'].iloc[_te].min()), "
                "df['date'].iloc[_tr].max().date(), df['date'].iloc[_te].min().date())"
            )
            executed = ex.execute(ex.with_appended_code_cell(mutated_node, probe))
            lines = ex.stdout_lines(executed, "WALDEAN_VERIFY_TEMPORAL_CV")
            if not lines:
                return False, {"reason": "no verify output"}
            _, flag, train_max, test_min = lines[-1].split()
            ok = int(flag) == 1
            return ok, {"variant": 1, "train_max_date": train_max, "test_min_date": test_min}


class TestSelectionMutation(Mutation):
    """Choose the model on the test split instead of the validation split,
    then report the chosen model on that same test split."""

    flaw_id = "leakage-test-selection"

    CONCLUSION = (
        "The best of the three models reaches the test ROC AUC and average "
        "precision printed above."
    )

    BEST_OF_N_CONCLUSION = (
        "The random forest reaches the test ROC AUC printed above."
    )
    BEST_OF_N_CELL = (
        "seed_aucs = []\n"
        "for s in range(20):\n"
        "    rf = RandomForestClassifier(n_estimators=100, min_samples_leaf=5, random_state=s).fit(X_tr, y_tr)\n"
        "    seed_aucs.append(roc_auc_score(y_te, rf.predict_proba(X_te)[:, 1]))\n"
        "best_auc = max(seed_aucs)\n"
        'print(f"forest test roc_auc={best_auc:.3f}")'
    )

    def applicable(self, nb_node) -> bool:
        m = meta(nb_node)
        return all(k in m for k in ("candidates_cell", "select_cell", "report_cell", "conclusion_cell"))

    def apply(self, nb_node, seed: int):
        m = meta(nb_node)
        variant = seed % 3
        if variant == 2:
            nb = _insert_code_cell(nb_node, m["conclusion_cell"], self.BEST_OF_N_CELL)
            return _replace_markdown(nb, m["conclusion_cell"] + 1, self.BEST_OF_N_CONCLUSION)
        if variant == 0:
            idx = m["candidates_cell"]
            src = nb_node.cells[idx]["source"]
            needle = "roc_auc_score(y_va, fitted[name].predict_proba(X_va)[:, 1])"
            if needle not in src:
                raise ValueError("validation scoring line not found in candidates_cell")
            nb = _replace_cell(nb_node, idx, src.replace(
                needle, "roc_auc_score(y_te, fitted[name].predict_proba(X_te)[:, 1])"))
        else:
            idx = m["select_cell"]
            src = nb_node.cells[idx]["source"]
            if "best = scores.idxmax()" not in src:
                raise ValueError("best = scores.idxmax() not found in select_cell")
            nb = _replace_cell(nb_node, idx, src.replace(
                "best = scores.idxmax()",
                "best = max(fitted, key=lambda n: roc_auc_score(y_te, fitted[n].predict_proba(X_te)[:, 1]))",
            ))
        return _replace_markdown(nb, m["conclusion_cell"], self.CONCLUSION)

    def _verify_best_of_n(self, mutated_node) -> tuple[bool, dict]:
        probe = (
            "print('WALDEAN_VERIFY_BESTOFN', len(seed_aucs), int(best_auc == max(seed_aucs)), "
            "float(np.mean(seed_aucs)), float(max(seed_aucs)))"
        )
        executed = ex.execute(ex.with_appended_code_cell(mutated_node, probe))
        lines = ex.stdout_lines(executed, "WALDEAN_VERIFY_BESTOFN")
        if not lines:
            return False, {"reason": "no verify output"}
        _, n, reports_max, mean, best = lines[-1].split()
        flow = analyze(from_nbnode(mutated_node))
        on_test = any(
            c.name == "roc_auc_score" and c.loop_depth > 0 and c.pos_args and "y_te" in c.pos_args[0]
            for c in flow.calls
        )
        ok = int(n) >= 10 and reports_max == "1" and float(best) > float(mean) and on_test
        return ok, {"variant": 2, "candidates": int(n), "reported": float(best),
                    "mean_over_candidates": float(mean), "selection_scores_are_test_scores": on_test}

    def verify(self, mutated_node) -> tuple[bool, dict]:
        if any("seed_aucs" in c["source"] for c in mutated_node.cells if c["cell_type"] == "code"):
            return self._verify_best_of_n(mutated_node)
        m = meta(mutated_node)
        variant = 1 if "key=lambda" in mutated_node.cells[m["select_cell"]]["source"] else 0
        probe = (
            "_t = {n: roc_auc_score(y_te, f.predict_proba(X_te)[:, 1]) for n, f in fitted.items()}\n"
            "_v = {n: roc_auc_score(y_va, f.predict_proba(X_va)[:, 1]) for n, f in fitted.items()}\n"
            "_used = sel_scores if " + str(variant) + " == 0 else _t\n"
            "print('WALDEAN_VERIFY_SELECT', int(all(abs(_used[n] - _t[n]) < 1e-12 for n in _t)), "
            "int(best == max(_t, key=_t.get)), int(abs(test_auc - max(_t.values())) < 1e-12), "
            "int(best == max(_v, key=_v.get)))"
        )
        executed = ex.execute(ex.with_appended_code_cell(mutated_node, probe))
        lines = ex.stdout_lines(executed, "WALDEAN_VERIFY_SELECT")
        if not lines:
            return False, {"reason": "no verify output"}
        _, on_test, picks_test_max, reports_max, agrees_with_val = lines[-1].split()
        flow = analyze(from_nbnode(mutated_node))
        sel_line_uses_test = any(
            c.name == "roc_auc_score" and c.pos_args and "y_te" in c.pos_args[0]
            and c.cell == (m["select_cell"] if variant else m["candidates_cell"])
            for c in flow.calls
        )
        ok = on_test == "1" and picks_test_max == "1" and reports_max == "1" and sel_line_uses_test
        return ok, {"variant": variant, "selection_scores_are_test_scores": on_test == "1",
                    "reported_test_auc_is_max_over_candidates": reports_max == "1",
                    "same_choice_as_validation": agrees_with_val == "1"}


class ResampleBeforeSplitMutation(Mutation):
    flaw_id = "leakage-resample-before-split"

    CONCLUSION = (
        "After balancing the classes, the model reaches the accuracy and AUC "
        "printed above on the held-out test set."
    )

    def applicable(self, nb_node) -> bool:
        m = meta(nb_node)
        return bool(m.get("imbalanced")) and bool(m.get("binary_col")) and "split_cell" in m

    def apply(self, nb_node, seed: int):
        m = meta(nb_node)
        col = m["binary_col"]
        if seed % 2 == 0:
            code = (
                "from sklearn.utils import resample\n"
                f"minority = df[df[{col!r}] == 1]\n"
                f"majority = df[df[{col!r}] == 0]\n"
                "df = pd.concat([majority, resample(minority, replace=True, "
                f"n_samples=len(majority), random_state={seed})])\n"
            )
        else:
            code = (
                f"minority = df[df[{col!r}] == 1]\n"
                "df = pd.concat([df, minority.sample(n=len(minority) * 4, replace=True, "
                f"random_state={seed})])\n"
            )
        code += f"X = df[num_cols]\ny = df[{col!r}]"
        nb = _insert_code_cell(nb_node, m["split_cell"], code)
        return _replace_markdown(nb, m["conclusion_cell"] + 1, self.CONCLUSION)

    def verify(self, mutated_node) -> tuple[bool, dict]:
        variant = 0 if any("resample(minority" in c["source"] for c in mutated_node.cells) else 1
        probe = (
            "print('WALDEAN_VERIFY_RESAMPLE', len(set(y_tr.index) & set(y_te.index)), len(y_te))"
        )
        executed = ex.execute(ex.with_appended_code_cell(mutated_node, probe))
        lines = ex.stdout_lines(executed, "WALDEAN_VERIFY_RESAMPLE")
        if not lines:
            return False, {"reason": "no verify output"}
        _, shared, n_test = lines[-1].split()
        return int(shared) > 0, {"variant": variant, "rows_in_both_splits": int(shared), "test_rows": int(n_test)}


MUTATIONS: list[Mutation] = [
    FitBeforeSplitMutation(),
    MultipleTestingMutation(),
    BaserateAccuracyMutation(),
    SurvivorshipMutation(),
    SignificanceMeaninglessMutation(),
    RegressionToMeanMutation(),
    TemporalShuffleMutation(),
    TestSelectionMutation(),
    ResampleBeforeSplitMutation(),
]
