"""Static (layer A) detectors: deterministic, key-free, evidence-bearing.

Every flag carries an exact location and mechanical evidence. Confidence is
a property of the detection (static facts ~0.9+, heuristic candidates
below the default floor); severity is a property of the flaw class and
comes from the taxonomy.
"""

from __future__ import annotations

import ast
import re
import textwrap

from ..analysis.dataflow import AssignEvent, CallSite, NotebookDataflow, _strip_magics, analyze
from ..analysis.ingest import ParsedNotebook
from ..core.flag import Flag
from ..core.taxonomy import load_taxonomy

TEST_FUNCS = {
    "ttest_ind", "ttest_rel", "ttest_1samp", "mannwhitneyu", "wilcoxon",
    "ks_2samp", "chi2_contingency", "fisher_exact", "pearsonr", "spearmanr",
    "kendalltau", "f_oneway", "kruskal", "binomtest", "proportions_ztest",
}
# word-bounded: 'stockholm' or a variable 'fdr_level' must not read as a correction
CORRECTION_RE = re.compile(
    r"\b(?:multipletests|bonferroni|holm|sidak|fdr_bh|fdr_by|fdr_tsbh|fdr_tsbky)\b",
    re.IGNORECASE,
)
OTHER_METRIC_RE = re.compile(
    r"roc_auc|f1_score|precision_score|recall_score|balanced_accuracy"
    r"|average_precision|classification_report|confusion_matrix|log_loss"
)
SURVIVOR_COLUMNS = {"status", "active", "is_active", "churned", "retained", "completed", "survived"}
# retained for mutate.verify's applicability check; the detector itself no
# longer fabricates an iteration count for loops (see detect_multiple_testing)
LOOP_TEST_WEIGHT = 10
MULTIPLE_TESTING_THRESHOLD = 5
IMBALANCE_THRESHOLD = 0.8


def _make_flag(flaw_id: str, confidence: float, cell: int, line: int, evidence: str, **extra) -> Flag:
    d = load_taxonomy()[flaw_id]
    return Flag(
        flaw_id=flaw_id,
        severity=d.severity,
        confidence=confidence,
        cell=cell,
        line=line,
        evidence=evidence,
        failure_scenario=d.failure_scenario,
        fix=d.fix,
        extra=extra,
    )


# classes whose .fit learns statistics that leak when computed on full data;
# estimators (.fit-only models) are a different flaw class and are not v1
TRANSFORMER_CLASSES = {
    "StandardScaler", "MinMaxScaler", "RobustScaler", "MaxAbsScaler", "Normalizer",
    "QuantileTransformer", "PowerTransformer", "PolynomialFeatures",
    "PCA", "KernelPCA", "TruncatedSVD", "NMF",
    "SimpleImputer", "KNNImputer", "IterativeImputer",
    "OneHotEncoder", "OrdinalEncoder",
    "CountVectorizer", "TfidfVectorizer", "TfidfTransformer",
    "SelectKBest", "SelectPercentile", "RFE", "VarianceThreshold",
    "Tokenizer",
}
FIT_METHODS = {"fit", "fit_transform", "fit_on_texts"}
# fitting a label encoding on full y is standard practice, not leakage
NON_LEAKY_TRANSFORMERS = {"LabelEncoder", "LabelBinarizer"}


STAT_METHODS = {"mean", "median", "std", "var", "min", "max", "quantile", "mode"}
GROUP_STAT_RE = re.compile(r"\b(?:mean|median|std|var|min|max|mode)\b")
COMPARE_RE = re.compile(r"[<>!=]=|[<>]")


# cross-validation calls are evaluation sinks too: a transformer fitted on
# the full data whose output feeds CV has seen every fold's test rows
CV_SINKS = {"cross_val_score", "cross_val_predict", "cross_validate"}
RESAMPLE_METHODS = {"fit_resample", "fit_sample"}
SKLEARN_RESAMPLE_RE = re.compile(r"from\s+sklearn\.utils\s+import[^\n]*\bresample\b")


def _join_names(names) -> str:
    ns = sorted(names)
    return ns[0] if len(ns) == 1 else ", ".join(ns[:-1]) + " and " + ns[-1]


# -- leakage-temporal-shuffle constants --
DATETIME_MAKERS = {"to_datetime", "date_range", "DatetimeIndex"}
DATE_READERS = {"read_csv", "read_parquet", "read_sql"}
# a lag/window METHOD call: the '.' before the verb is load-bearing — it
# distinguishes df['y'].shift(1) (a series method, real lag) from a bare
# shift(image, ...)/np.diff(...) that merely shares the name
LAG_FUNC_RE = re.compile(r"\.(shift|rolling|resample|diff|pct_change|ewm|expanding|asfreq)\(")
# base segments that make the lag name a namespaced free function, not a
# frame method: scipy.ndimage.shift, np.diff, sklearn's utils are not lags
MODULE_ALIASES = {"np", "numpy", "pd", "pandas", "scipy", "sp", "tf", "torch"}
TEMPORAL_SORT_INDEX_RE = re.compile(
    r"(?:set_index|sort_values)\(\s*(?:by\s*=\s*)?['\"]\w*(?:date|datetime|timestamp|dteday)\w*['\"]",
    re.IGNORECASE,
)
# any set_index/sort_values on a LITERAL column, capturing the column name; a
# match whose column is NOT date-like means the frame's row order is a
# value ordering, not time — so an A1-only datetime column (an unused parsed
# date) does not make a .shift/.diff a temporal lag (see the value-sorted FPs)
SORT_INDEX_COLUMN_RE = re.compile(
    r"(?:set_index|sort_values)\(\s*(?:by\s*=\s*)?['\"](\w+)['\"]",
    re.IGNORECASE,
)
DATE_COLUMN_RE = re.compile(r"date|datetime|timestamp|dteday", re.IGNORECASE)
# splitters that shuffle unconditionally (KFold/StratifiedKFold shuffle only
# when shuffle=True, handled separately; TimeSeriesSplit never does)
SHUFFLED_SPLITTERS = {"ShuffleSplit", "StratifiedShuffleSplit"}
_TEMPORAL_SPLITTERS = SHUFFLED_SPLITTERS | {"KFold", "StratifiedKFold", "TimeSeriesSplit"}


def detect_leakage_temporal_shuffle(nb: ParsedNotebook, flow: NotebookDataflow) -> list[Flag]:
    sinks = [c for c in flow.calls if c.name == "train_test_split" or c.name in CV_SINKS]
    if not sinks:
        return []
    src = {c.index: c.source.splitlines() for c in nb.code_cells}

    def is_lag(ev) -> bool:
        if ev.call is None:
            return False
        if not LAG_FUNC_RE.search(ev.call.func + "("):
            return False
        base = re.split(r"[.\[]", ev.call.func, maxsplit=1)[0]
        return base not in MODULE_ALIASES

    def lag_label(ev) -> str:
        assert ev.call is not None
        m = LAG_FUNC_RE.search(ev.call.func + "(")
        assert m is not None
        return f"`.{m.group(1)}` at cell {ev.cell} line {ev.line}"

    def classify_splitter(ctor) -> str:
        if ctor.name == "TimeSeriesSplit":
            return "skip"
        if ctor.name in SHUFFLED_SPLITTERS:
            return "shuffled"
        if ctor.name in {"KFold", "StratifiedKFold"}:
            return "shuffled" if ctor.kw_args.get("shuffle") == {"True"} else "plain"
        return "plain"

    def cv_state(s) -> str:
        cv = s.kw_args.get("cv")
        if not cv:  # absent, or an int literal (no names) -> default plain CV
            return "plain"
        for name in cv:
            ev = flow.last_assign(name, (s.cell, s.line))
            if ev is not None and ev.call is not None:
                return classify_splitter(ev.call)
        for c in flow.calls:  # inline constructor: cv=KFold(5, shuffle=True)
            if (c.cell, c.line) == (s.cell, s.line) and c.name in _TEMPORAL_SPLITTERS:
                return classify_splitter(c)
        return "plain"

    def sink_state(s) -> str:
        if s.name == "train_test_split":
            shuffle = s.kw_args.get("shuffle")
            if shuffle is None or shuffle == {"True"}:
                return "shuffled"
            if shuffle == {"False"}:
                return "skip"
            return "skip"  # non-literal shuffle: treat as clean (FP discipline)
        return cv_state(s)

    flags: list[Flag] = []
    for s in sinks:
        if s.name in CV_SINKS:
            seed = set().union(
                set(), *s.pos_args[1:3],
                s.kw_args.get("X", set()), s.kw_args.get("y", set()),
            )
        else:
            seed = s.arg_names
        events, _bindings = flow.chain(seed, (s.cell, s.line))
        chain_text = "\n".join(
            src[ev.cell][ev.line - 1]
            for ev in events
            if ev.cell in src and 0 < ev.line <= len(src[ev.cell])
        )

        dt_events = [
            ev for ev in events
            if ev.call is not None and (
                ev.call.name in DATETIME_MAKERS
                or (ev.call.name in DATE_READERS and "parse_dates" in ev.call.kw_args)
            )
        ]
        a1 = any(ev.call is not None and ev.call.name in DATETIME_MAKERS for ev in dt_events)
        a2 = any(ev.call is not None and ev.call.name in DATE_READERS for ev in dt_events)
        a3 = bool(TEMPORAL_SORT_INDEX_RE.search(chain_text))
        a_any = a1 or a2 or a3
        a_strong = a2 or a3
        if not a_any:
            continue
        # A1 (a bare to_datetime column) is weak temporal identity: it can be an
        # unused parsed date on a frame whose rows are ordered by value. When the
        # only signal is A1 and the chain sorts on a non-date column, the frame is
        # value-sorted, not time-sorted, so a lag/window method is cross-sectional,
        # not a temporal lag — emit nothing (kills the value-sorted FPs).
        if a1 and not a_strong and any(
            not DATE_COLUMN_RE.search(m.group(1))
            for m in SORT_INDEX_COLUMN_RE.finditer(chain_text)
        ):
            continue

        lag_events = [ev for ev in events if is_lag(ev)]
        has_lag = bool(lag_events)
        state = sink_state(s)
        if state == "skip":
            continue

        if a_any and has_lag and state == "shuffled":
            confidence = 0.9
        elif a_any and has_lag and state == "plain":
            confidence = 0.75
        elif a_strong and not has_lag and s.name == "train_test_split" and state == "shuffled":
            confidence = 0.6
        else:
            continue

        dt_cell = dt_events[0].cell if dt_events else s.cell
        if has_lag:
            lag_desc = ", ".join(lag_label(ev) for ev in lag_events)
            evidence = (
                f"time-ordered frame (datetime origin in cell {dt_cell}) carries "
                f"lag/window features ({lag_desc}); `{s.name}` (cell {s.cell}) uses a "
                f"{'shuffled' if state == 'shuffled' else 'non-temporal'} split, "
                f"leaking future rows into training"
            )
        else:
            evidence = (
                f"time-ordered frame (datetime origin in cell {dt_cell}) is split by a "
                f"shuffled `train_test_split` (cell {s.cell}); no lag features detected, "
                f"but shuffling time-ordered rows risks leakage (candidate)"
            )
        flags.append(
            _make_flag(
                "leakage-temporal-shuffle",
                confidence=confidence,
                cell=s.cell,
                line=s.line,
                evidence=evidence,
                sink=s.name,
            )
        )
    return flags


def detect_leakage_fit_before_split(nb: ParsedNotebook, flow: NotebookDataflow) -> list[Flag]:
    sinks = [c for c in flow.calls if c.name == "train_test_split" or c.name in CV_SINKS] + flow.slice_splits()
    if not sinks:
        return []

    # names assigned from a train_test_split call (X_train, X_test, ...)
    split_outputs: set[str] = set()
    split_binds: set[tuple[str, int | None]] = set()
    test_binds: set[tuple[str, int | None]] = set()
    for ev in flow.assigns:
        if ev.call is not None and ev.call.name == "train_test_split":
            split_outputs |= ev.targets
            split_binds |= {(t, id(ev)) for t in ev.targets}
            test_binds |= {(t, id(ev)) for t in ev.ordered_targets[1::2]}
    # every .transform call, for binding-aware receiver checks
    transform_calls = [c for c in flow.calls if c.name == "transform" and c.receiver]
    assign_event_of: dict[int, AssignEvent] = {
        id(ev.call): ev for ev in flow.assigns if ev.call is not None
    }

    def recv_class(call) -> str | None:
        """Class the receiver was constructed from, resolved at the call's
        position (a later rebind of the name must not rewrite history)."""
        if call.receiver.endswith("()"):
            # direct-constructor receiver: StandardScaler().fit(X). Factory
            # calls (clone(x).fit, make_pipeline(...).fit) resolve to the
            # factory name, which is not a known transformer class — so the
            # known-class rule stays conservative for them.
            head = call.receiver[:-2]
            return head if head.isidentifier() else None
        ev = flow.last_assign(call.receiver, (call.cell, call.line))
        return ev.call.name if ev is not None and ev.call is not None else None

    def same_receiver(a_call, b_call) -> bool:
        """Both calls act on the same object: same receiver name bound to
        the same event at each site (name reuse across sections differs)."""
        return (
            a_call.receiver == b_call.receiver
            and flow.binding(a_call.receiver, (a_call.cell, a_call.line))
            == flow.binding(b_call.receiver, (b_call.cell, b_call.line))
        )

    # flow-sensitive dependency chain per sink (kill-on-reassign: name reuse
    # across notebook sections no longer links unrelated datasets)
    chains = []
    for s in sinks:
        if s.name in CV_SINKS:
            # only the data args (X, y): the estimator is cloned and refit per
            # fold, and cv=/groups=/scoring= carry no transformed data
            seed = set().union(
                set(), *s.pos_args[1:3],
                s.kw_args.get("X", set()), s.kw_args.get("y", set()),
            )
        else:
            seed = s.arg_names
        events, bindings = flow.chain(seed, (s.cell, s.line))
        chains.append((s, {id(e) for e in events}, bindings))

    calls_in_order = sorted(flow.calls, key=lambda c: (c.cell, c.line))

    call_binds: dict[int, set] = {}

    def binds_of(c) -> set:
        if id(c) not in call_binds:
            names = c.arg_names | ({c.receiver_base} if c.receiver_base else set())
            call_binds[id(c)] = flow.chain(names, (c.cell, c.line), mutations=True)[1]
        return call_binds[id(c)]

    def reaches_score(call, reached: set) -> bool:
        reached = set(reached)
        for c in calls_in_order:
            at = (c.cell, c.line)
            if at < (call.cell, call.line) or c is call:
                continue
            if not binds_of(c) & reached:
                continue
            if c.name in PREDICT_CALLS or c.name in SCORE_FUNCS or c.name in CV_SINKS or c.name == "score":
                return True
            if c.name == "fit" and c.receiver_base and c.receiver_base.isidentifier():
                reached.add(flow.binding(c.receiver_base, at, mutations=True))
        return False

    best: dict[object, Flag] = {}

    def emit(call, confidence, leaked, evidence, key=None, sink_cell=None, **more):
        key = key if key is not None else id(call)
        if key in best and best[key].confidence >= confidence:
            return
        extra = {"leaked_names": sorted(leaked), **more}
        if sink_cell is not None:
            extra["sink_cell"] = sink_cell
        if call.helper_local:
            extra["helper_local"] = True
        best[key] = _make_flag(
            "leakage-fit-before-split",
            confidence=confidence,
            cell=call.cell,
            line=call.line,
            evidence=evidence,
            **extra,
        )

    for call in flow.calls:
        pos = (call.cell, call.line)

        # -- transformer fitted on data that reaches an evaluation sink --
        if call.name in FIT_METHODS and call.receiver is not None:
            if "[?]" in call.receiver:
                continue  # dynamic container element: object identity unknown
            cls = recv_class(call)
            if cls in NON_LEAKY_TRANSFORMERS:
                continue
            is_transformer = (
                call.name == "fit_transform"
                or call.name == "fit_on_texts"
                or cls in TRANSFORMER_CLASSES
                or any(same_receiver(call, t) for t in transform_calls)
            )
            if not is_transformer:
                continue  # estimator fit: not this flaw class
            my_event = assign_event_of.get(id(call))
            arg_binds = {flow.binding(n, pos) for n in call.arg_names}
            recv_bind = flow.binding(call.receiver, pos)
            transforms_split_part = any(
                same_receiver(call, t) and t.arg_names & split_outputs
                for t in transform_calls
            )
            _, arg_chain = flow.chain(call.arg_names, pos)
            touched_test = {n for n, _ in arg_chain & test_binds}
            if touched_test:
                reached: set[tuple[str, int | None]] = (
                    {(t, id(my_event)) for t in my_event.targets} if my_event is not None else set())
                if call.receiver_base and call.receiver_base.isidentifier():
                    reached.add(flow.binding(call.receiver_base, pos, mutations=True))
                scored = reaches_score(call, reached)
                emit(call, 0.9 if scored else 0.75, touched_test, (
                    f"`{call.func}(...)` is fitted on {_join_names(touched_test)}, "
                    f"a test split output; the transformer learns from the rows it is scored on"
                    + ("" if scored else "; no later scoring call reads its output (candidate)")
                ))
                continue
            for sink, chain_ids, bindings in chains:
                leaked = {name for name, ev_id in arg_binds if (name, ev_id) in bindings}
                if not leaked:
                    continue
                # the fitted data reaches the sink either through this call's
                # assigned result, or through the receiver's .transform output
                # (a bare `skb.fit(X, y)` produces no assign event)
                on_chain = (my_event is not None and id(my_event) in chain_ids) or recv_bind in bindings
                if sink.name in {"train_test_split", "slice_split"}:
                    # (a) its output feeds the split, or (b) the fitted
                    # receiver later transforms a split output
                    if not (on_chain or transforms_split_part):
                        continue
                    how = "`train_test_split`" if sink.name == "train_test_split" else "a row slice split"
                    emit(call, 0.92, leaked, (
                        f"`{call.func}(...)` consumes {_join_names(leaked)}, "
                        f"feeding {how} (cell {sink.cell}) — "
                        f"the fit happened before the split"
                    ), sink_cell=sink.cell, sink=sink.name, receiver=call.receiver, arg=probe_arg(call))
                else:
                    if not on_chain:
                        continue
                    # supervised selection on full data (fit(X, y)) is the
                    # serious variant; unsupervised pre-CV fits are common
                    # practice and stay below the confidence floor
                    supervised = len(call.pos_args) >= 2 or "y" in call.kw_args
                    emit(call, 0.9 if supervised else 0.75, leaked, (
                        f"`{call.func}(...)` is fitted on {_join_names(leaked)} whose "
                        f"transformed output feeds `{sink.name}` (cell {sink.cell}); "
                        f"every CV fold's test rows were in the transformer fit"
                        + (" (fitted with labels)" if supervised else "")
                    ), sink_cell=sink.cell, sink=sink.name, receiver=call.receiver, arg=probe_arg(call))

        # -- imputation with statistics of the same frame, before the split --
        elif call.name in {"fillna", "replace"} and call.receiver is not None:
            base = call.receiver_base
            if base is None:
                continue
            base_bind = flow.binding(base, pos)
            _, arg_bindings = flow.chain(call.arg_names, pos)
            if base_bind not in arg_bindings:
                continue  # fill values do not derive from the frame itself
            _, base_chain = flow.chain({base}, pos)
            filled_test = {n for n, _ in base_chain & test_binds}
            if filled_test and not base_chain & (split_binds - test_binds):
                emit(call, 0.85, filled_test, (
                    f"`{call.func}(...)` fills `{base}` with statistics of {_join_names(filled_test)}, "
                    f"a test split output; the imputation learns from the rows it is scored on"
                ), key=f"impute:{base}")
                continue
            for sink, _ids, bindings in chains:
                if sink.name not in {"train_test_split", "slice_split"}:
                    continue
                if base_bind in bindings and pos < (sink.cell, sink.line):
                    # one flag per frame: imputing N columns is one violation
                    how = "`train_test_split`" if sink.name == "train_test_split" else "a row slice split"
                    emit(call, 0.85, {base}, (
                        f"`{call.func}(...)` fills values of `{base}` with statistics "
                        f"computed on the full `{base}` before {how} "
                        f"(cell {sink.cell}); imputation statistics include the test rows"
                    ), key=f"impute:{base}")
                    break

    src = {c.index: c.source.splitlines() for c in nb.code_cells}
    for ev in flow.assigns:
        end = max(ev.end_line, ev.line)
        text = "\n".join(src.get(ev.cell, [])[ev.line - 1:end])
        if COMPARE_RE.search(text):
            continue
        for base in ev.targets & ev.sources:
            stats = [
                c for c in flow.calls
                if c.cell == ev.cell and ev.line <= c.line <= end and c.receiver_base == base and (
                    (c.name in STAT_METHODS and c.receiver is not None and "(" not in c.receiver)
                    or (c.name in {"transform", "apply"} and c.receiver is not None
                        and c.receiver.startswith(f"{base}.groupby") and GROUP_STAT_RE.search(text))
                )
            ]
            if not stats:
                continue
            stat = stats[0]
            for sink, chain_ids, _bindings in chains:
                if id(ev) not in chain_ids:
                    continue
                if sink.name in {"train_test_split", "slice_split"}:
                    how = "`train_test_split`" if sink.name == "train_test_split" else "a row slice split"
                    emit(stat, 0.85, {base}, (
                        f"`{stat.func}(...)` is computed over the full `{base}` and written back "
                        f"into `{base}` before {how} (cell {sink.cell}); "
                        f"the statistic includes the test rows"
                    ), key=f"impute:{base}", sink_cell=sink.cell, sink=sink.name)
                else:
                    emit(stat, 0.75, {base}, (
                        f"`{stat.func}(...)` is computed over the full `{base}` and written back "
                        f"into `{base}` whose rows feed `{sink.name}` (cell {sink.cell}); "
                        f"every CV fold's test rows were in the statistic"
                    ), key=f"impute:{base}", sink_cell=sink.cell, sink=sink.name)
                break

    impute_at: dict[tuple[int, int], str] = {}
    for key in [k for k in best if isinstance(k, str) and k.startswith("impute:")]:
        at = (best[key].cell, best[key].line)
        other = impute_at.setdefault(at, key)
        if other == key:
            continue
        ranked = sorted((other, key), key=lambda k: (
            flow.binding(k.removeprefix("impute:"), at)[1] is not None, best[k].confidence))
        del best[ranked[0]]
        impute_at[at] = ranked[1]

    return list(best.values())


def detect_multiple_testing(nb: ParsedNotebook, flow: NotebookDataflow) -> list[Flag]:
    sites = [c for c in flow.calls if c.name in TEST_FUNCS]
    if not sites:
        return []
    if CORRECTION_RE.search(nb.full_source()):
        return []
    n_static = len(sites)
    fwer = 1 - 0.95 ** n_static
    # FWER is only reported from the statically counted sites — never from a
    # fabricated per-loop iteration count
    over_threshold = n_static > MULTIPLE_TESTING_THRESHOLD
    param_vars = sorted(set().union(set(), *(c.arg_names & c.loop_vars for c in sites)))
    if param_vars:
        # loop variable reaches the test arguments: the loop enumerates
        # hypotheses, one per iteration
        confidence = 0.9
        evidence = (
            f"{n_static} test call site(s); at least one parameterized by a loop "
            f"over `{param_vars[0]}` — per-iteration hypotheses, iteration count "
            f"not statically known; no correction found"
            + (f"; FWER at alpha=0.05 from the static sites alone: {fwer:.0%}"
               if over_threshold else "")
        )
    elif over_threshold:
        confidence = 0.9
        evidence = (
            f"{n_static} test call site(s), no correction found; "
            f"FWER at alpha=0.05: {fwer:.0%}"
        )
    elif any(c.loop_depth > 0 for c in sites):
        # loop variable never reaches the test arguments: likely a
        # resampling/permutation loop over a single hypothesis
        confidence = 0.75
        evidence = (
            f"{n_static} test call site(s) inside a loop whose variable does not "
            f"reach the test arguments — likely resampling over one hypothesis "
            f"(candidate); no correction found"
        )
    else:
        return []
    extra: dict[str, int | float] = {"n_tests": n_static}
    if over_threshold:
        extra["fwer"] = round(fwer, 3)
    first = sites[0]
    return [
        _make_flag(
            "testing-multiple-uncorrected",
            confidence=confidence,
            cell=first.cell,
            line=first.line,
            evidence=evidence,
            **extra,
        )
    ]


_VC_COLUMN_RE = re.compile(r"\[['\"](\w+)['\"]\]|\.(\w+)$")


def _imbalance_from_outputs(nb: ParsedNotebook, flow: NotebookDataflow,
                            y_names: set[str], at: tuple[int, int]) -> float | None:
    """Majority share parsed from a value_counts stored output, but only when
    the counted series links to the scored target: a plain-name receiver whose
    binding is on y's dependency chain, or a column receiver whose literal
    column name appears in a y-chain assignment line. A skewed unrelated
    feature must not drive the base-rate verdict, and an unrelated balanced
    one must not clear it."""
    events, bindings = flow.chain(y_names, at)
    src = {c.index: c.source.splitlines() for c in nb.code_cells}
    chain_text = "\n".join(
        src[ev.cell][ev.line - 1]
        for ev in events
        if ev.cell in src and 0 < ev.line <= len(src[ev.cell])
    )
    outputs = {c.index: c.outputs_text for c in nb.code_cells}
    for vc in flow.calls:
        if vc.name != "value_counts" or vc.receiver is None:
            continue
        out = outputs.get(vc.cell, "")
        if not out:
            continue
        m = _VC_COLUMN_RE.search(vc.receiver)
        col = (m.group(1) or m.group(2)) if m else None
        if col is None:
            linked = flow.binding(vc.receiver, (vc.cell, vc.line)) in bindings
        else:
            linked = f"'{col}'" in chain_text or f'"{col}"' in chain_text
        if not linked:
            continue
        values = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                try:
                    values.append(float(parts[-1]))
                except ValueError:
                    continue
        if len(values) >= 2 and sum(values) > 0:
            return max(values) / sum(values)
    return None


def detect_baserate_accuracy(nb: ParsedNotebook, flow: NotebookDataflow) -> list[Flag]:
    acc_calls = [c for c in flow.calls if c.name == "accuracy_score"]
    if not acc_calls:
        return []
    if OTHER_METRIC_RE.search(nb.full_source()):
        return []
    first = acc_calls[0]
    y_names = first.pos_args[0] if first.pos_args else first.kw_args.get("y_true", set())
    majority = _imbalance_from_outputs(nb, flow, y_names, (first.cell, first.line))
    if majority is not None and majority < IMBALANCE_THRESHOLD:
        return []  # accuracy-only is defensible on balanced classes
    if majority is None:
        confidence, note = 0.55, "class balance not visible in outputs (candidate)"
    else:
        confidence, note = 0.9, f"majority class share {majority:.0%} visible in value_counts output"
    return [
        _make_flag(
            "baserate-accuracy-imbalanced",
            confidence=confidence,
            cell=first.cell,
            line=first.line,
            evidence=f"accuracy is the only classification metric; {note}",
            majority_share=majority,
        )
    ]


SURVIVOR_FILTER_RE = re.compile(
    r"(\w+)\s*=\s*\1\[\s*\1(?:\.(\w+)|\[\s*[\"'](\w+)[\"']\s*\])\s*(?:==|!=)",
)
# self-filter via .query, e.g. df = df.query("status == 'active'"), including
# chained .query calls; the column is the first (optionally backtick-quoted)
# identifier before the comparison operator. An f-string or non-literal query
# expression is unresolvable and skipped — no guessing.
SURVIVOR_QUERY_ASSIGN_RE = re.compile(r"(\w+)\s*=\s*\1\b[^\n]*")
SURVIVOR_QUERY_STRING_RE = re.compile(r"\.query\(\s*([A-Za-z]*)([\"'])(.*?)\2")
SURVIVOR_QUERY_COND_RE = re.compile(r"^\s*`?(\w+)`?\s*(?:==|!=)")


def _survivor_filter_columns(source: str):
    """Yield (match_start, risk_column) for every self-scoping cohort filter
    in a cell, across both the subscript and .query idioms."""
    for m in SURVIVOR_FILTER_RE.finditer(source):
        yield m.start(), (m.group(2) or m.group(3) or "").lower()
    for am in SURVIVOR_QUERY_ASSIGN_RE.finditer(source):
        for qm in SURVIVOR_QUERY_STRING_RE.finditer(am.group(0)):
            if "f" in qm.group(1).lower():
                continue  # f-string: the filter expression is dynamic
            cm = SURVIVOR_QUERY_COND_RE.match(qm.group(3))
            if cm:
                yield am.start() + qm.start(), cm.group(1).lower()


def detect_survivorship_candidate(nb: ParsedNotebook, flow: NotebookDataflow) -> list[Flag]:
    """Static half of the survivorship pair: a filter on a risk-vocabulary
    column followed by aggregation. Low confidence by design — promotion to
    a real flag requires the narrative layer confirming a population claim."""
    flags = []
    for cell in nb.code_cells:
        if cell.index in flow.skipped_cells:
            continue  # oversized/deep cell dataflow skipped: keep runtime bounded
        for start, column in _survivor_filter_columns(cell.source):
            if column not in SURVIVOR_COLUMNS:
                continue
            aggregates_later = any(
                c.name in {"groupby", "mean", "agg", "sum", "median", "pivot_table"}
                and c.cell >= cell.index
                for c in flow.calls
            )
            if not aggregates_later:
                continue
            line = cell.source[:start].count("\n") + 1
            flags.append(
                _make_flag(
                    "selection-survivorship-cohort",
                    confidence=0.55,
                    cell=cell.index,
                    line=line,
                    evidence=(
                        f"cohort filtered on `{column}` (a survival-correlated column) "
                        f"and aggregated afterwards; whether the conclusion is scoped "
                        f"to survivors needs the narrative layer"
                    ),
                    column=column,
                )
            )
    return flags


SCORE_FUNCS = {
    "roc_auc_score", "average_precision_score", "f1_score", "fbeta_score", "precision_score",
    "recall_score", "accuracy_score", "balanced_accuracy_score", "log_loss", "brier_score_loss",
    "matthews_corrcoef", "cohen_kappa_score", "r2_score", "mean_squared_error",
    "mean_absolute_error", "root_mean_squared_error", "mean_absolute_percentage_error",
    "precision_recall_curve", "roc_curve",
}
CV_SCORERS = {"cross_val_score", "cross_validate"}
PREDICT_CALLS = {"predict", "predict_proba", "decision_function", "cross_val_predict"}
SELECT_RE = re.compile(
    r"\.(?:idxmax|idxmin|argmax|argmin|nanargmax|nanargmin)\("
    r"|\b(?:max|min|sorted)\([^\n]*\bkey\s*="
    r"|\.(?:index|iloc)\[0\]"
)
ARGBEST_RE = re.compile(
    r"\.(?:idxmax|idxmin|argmax|argmin|nanargmax|nanargmin)\(|\b(?:max|min|sorted)\([^\n]*\bkey\s*="
)
SORT_RE = re.compile(r"\.(?:sort_values|nlargest|nsmallest|sort_index)\(|\bsorted\(")
FIRST_TRUE_RE = re.compile(r"\([^()]*(?:>=|<=|==|!=|>|<)[^()]*\)\s*\.(?:argmax|idxmax|argmin|idxmin)\(")
ROW_SELECT_RE = re.compile(r"\.iloc\[0\]\s*$|\.loc\[[^\n]*\.(?:idxmax|idxmin|argmax|argmin)\(")
IFEXP_RE = re.compile(r"\bif\b[^\n]*\belse\b")
ATTR_PASSTHROUGH_RE = re.compile(r"^\w+\s*=\s*\w+\.(?:values|T)\s*(?:;|$)")
LABEL_PASSTHROUGH = {"to_numpy", "values", "copy", "astype", "reset_index", "ravel", "squeeze"}
DEF_RE = re.compile(r"^def (\w+)\(", re.MULTILINE)
MAX_CALLS = {"max", "nanmax"}
SUMMARY_CALLS = {"mean", "nanmean", "median", "nanmedian", "std", "nanstd", "describe"}
LOOP_TEXT_RE = re.compile(r"\bfor\b")


def _metric_functions(nb: ParsedNotebook) -> set[str]:
    names = set(SCORE_FUNCS)
    for cell in nb.code_cells:
        lines = cell.source.splitlines()
        for m in DEF_RE.finditer(cell.source):
            start = cell.source[:m.start()].count("\n")
            body = []
            for line in lines[start + 1:]:
                if line.strip() and not line[:1].isspace():
                    break
                body.append(line)
            if any(re.search(rf"\b{f}\b", "\n".join(body)) for f in SCORE_FUNCS):
                names.add(m.group(1))
    return names


def _compares_named_scores(text: str, targets: set[str]) -> bool:
    try:
        tree = ast.parse(textwrap.dedent(text))
    except (SyntaxError, RecursionError, MemoryError):
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.IfExp):
            continue
        if not {n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name)} & targets:
            continue
        e = node.value
        if not (isinstance(e.body, ast.Constant) and isinstance(e.body.value, str)
                and isinstance(e.orelse, ast.Constant) and isinstance(e.orelse.value, str)):
            continue
        t = e.test
        if not (isinstance(t, ast.Compare) and len(t.ops) == 1 and isinstance(t.ops[0], (ast.Gt, ast.GtE, ast.Lt, ast.LtE))):
            continue
        left, right = t.left, t.comparators[0]
        if not (isinstance(left, ast.Subscript) and isinstance(right, ast.Subscript)):
            continue
        kl, kr = (
            {c.value for s in ast.walk(o) if isinstance(s, ast.Subscript) for c in ast.walk(s.slice) if isinstance(c, ast.Constant)}
            for o in (left, right)
        )
        a, b = e.body.value, e.orelse.value
        if (a in kl and b in kr) or (b in kl and a in kr):
            return True
    return False


def _wrapper_labels(nb: ParsedNotebook, flow: NotebookDataflow) -> dict[str, tuple[list[str], list[str], set[str]]]:
    out = {}
    for cell in nb.code_cells:
        try:
            tree = ast.parse(_strip_magics(cell.source))
        except (SyntaxError, RecursionError, MemoryError):
            continue
        for fn in tree.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            a = fn.args
            positional = [p.arg for p in a.posonlyargs + a.args]
            kwonly = [p.arg for p in a.kwonlyargs]
            local = {n.id for stmt in fn.body for n in ast.walk(stmt) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
            local |= {p.arg for p in (a.vararg, a.kwarg) if p is not None}
            end = fn.end_lineno or fn.lineno
            names: set[str] = set()
            body = flow.functions[fn.name].calls if fn.name in flow.functions else flow.calls
            for c in body:
                if c.cell == cell.index and fn.lineno < c.line <= end and c.name in SCORE_FUNCS:
                    names |= c.pos_args[0] if c.pos_args else c.kw_args.get("y_true", set())
            names = {n for n in names if n in positional or n in kwonly or n not in local}
            if names:
                out[fn.name] = (positional, kwonly, names)
    return out


def detect_leakage_test_selection(nb: ParsedNotebook, flow: NotebookDataflow) -> list[Flag]:
    metric_names = _metric_functions(nb)
    wrappers = _wrapper_labels(nb, flow)
    src = {c.index: c.source.splitlines() for c in nb.code_cells}
    calls_by_cell: dict[int, list] = {}
    for c in flow.calls:
        if c.inlined_from is None or (c.inlined_from not in wrappers and c.name not in SCORE_FUNCS):
            calls_by_cell.setdefault(c.cell, []).append(c)

    def span_text(ev) -> str:
        lines = src.get(ev.cell, [])
        return "\n".join(lines[ev.line - 1:max(ev.end_line, ev.line)])

    def printed_directly(mx: CallSite) -> bool:
        text = src.get(mx.cell, [""] * mx.line)[mx.line - 1]
        start = text.find("print(")
        if start < 0:
            return False
        for m in re.finditer(re.escape(mx.func) + r"\(", text):
            if m.start() < start or (m.start() > 0 and (text[m.start() - 1].isalnum() or text[m.start() - 1] in "_.")):
                continue
            opens = []
            for i in range(start + len("print"), m.start()):
                if text[i] == "(":
                    opens.append(i)
                elif text[i] == ")" and opens:
                    opens.pop()
            if any(not (text[o - 5:o] == "print" or text[o - 7:o] == ".format") for o in opens):
                continue
            depth, end = 0, m.end() - 1
            for end in range(m.end() - 1, len(text)):
                depth += (text[end] == "(") - (text[end] == ")")
                if depth == 0:
                    break
            before, after = text[:m.start()].rstrip(), text[end + 1:].lstrip()
            if re.match(r"[<>=!]", after) or re.search(r"[<>=!]$", before):
                continue
            return True
        return False

    def calls_in(ev) -> list:
        end = max(ev.end_line, ev.line)
        return [c for c in calls_by_cell.get(ev.cell, []) if ev.line <= c.line <= end]

    def is_metric(c) -> bool:
        return c.name in metric_names or c.name in CV_SCORERS or (c.name == "score" and c.receiver is not None)

    def label_names(c) -> set[str]:
        if c.name in wrappers and c.name not in SCORE_FUNCS:
            positional, kwonly, inner = wrappers[c.name]
            out: set[str] = set()
            for n in inner:
                if n in positional and positional.index(n) < len(c.pos_args):
                    out |= c.pos_args[positional.index(n)]
                elif n in positional or n in kwonly:
                    out |= c.kw_args.get(n, set())
                else:
                    out.add(n)
            return out
        if c.name in CV_SCORERS:
            return c.pos_args[2] if len(c.pos_args) > 2 else c.kw_args.get("y", set())
        if c.name == "score":
            return c.pos_args[1] if len(c.pos_args) > 1 else c.kw_args.get("y", set())
        return c.pos_args[0] if c.pos_args else c.kw_args.get("y_true", set())

    def canonical(names: set[str], at: tuple[int, int]) -> frozenset:
        out: set = set()
        frontier = [(n, at) for n in names]
        seen: set = set()
        while frontier:
            n, pos = frontier.pop()
            if (n, pos) in seen:
                continue
            seen.add((n, pos))
            ev = flow.last_assign(n, pos)
            if ev is not None and (
                (ev.call is not None and ev.call.name in LABEL_PASSTHROUGH)
                or (ev.call is None and ATTR_PASSTHROUGH_RE.match(src.get(ev.cell, [""] * ev.line)[ev.line - 1][ev.col:]))
            ):
                frontier.extend((s, (ev.cell, ev.line)) for s in ev.sources)
            else:
                out.add((n, id(ev) if ev is not None else None))
        return frozenset(out)

    def score_bearing(name: str, at: tuple[int, int] | tuple[int, int, int]) -> bool:
        own = flow.last_assign(name, at, mutations=True)
        if own is not None and SELECT_RE.search(span_text(own)):
            return False
        events, _ = flow.chain({name}, at, mutations=True)
        return any(is_metric(c) or c.name in PREDICT_CALLS for ev in events for c in calls_in(ev))

    def has_fresh_eval(after: tuple[int, int], labels: set, targets: set[str] | None) -> bool:
        known = [lab for lab in labels if lab]
        for m in flow.calls:
            at = (m.cell, m.line)
            if at <= after or not is_metric(m):
                continue
            lab = canonical(label_names(m), at)
            if not lab or any(lab <= k or k <= lab for k in known):
                continue
            if targets is None:
                return True
            _, binds = flow.chain(m.arg_names - label_names(m), at, mutations=True)
            if {n for n, _ in binds} & targets:
                return True
        return False

    statements = [((ev.cell, ev.line, ev.col), ev.sources) for ev in flow.assigns] + [
        ((c.cell, c.line), c.arg_names | ({c.receiver_base} if c.receiver_base else set()))
        for c in flow.calls
    ]
    flags: list[Flag] = []
    for sel in flow.assigns:
        text = span_text(sel)
        if not SELECT_RE.search(text) and not (
            IFEXP_RE.search(text) and (sum(c.name in metric_names for c in calls_in(sel)) >= 2 or _compares_named_scores(text, sel.targets))
        ):
            continue
        if FIRST_TRUE_RE.search(text) and not re.search(r"\b(?:max|min|sorted)\([^\n]*\bkey\s*=", text):
            continue
        pos = (sel.cell, sel.line)
        chain_events, chain_binds = flow.chain(sel.sources, pos, mutations=True)
        if SELECT_RE.search(text) and not ARGBEST_RE.search(text) and not any(
            SORT_RE.search(span_text(ev)) for ev in chain_events + [sel]
        ):
            continue
        metrics =[c for ev in chain_events + [sel] for c in calls_in(ev) if is_metric(c)]
        if not metrics:
            continue
        selected = {(t, id(sel)) for t in sel.targets}
        labels = {canonical(label_names(m), (m.cell, m.line)) for m in metrics}
        labels.discard(frozenset())
        row_pick = bool(ROW_SELECT_RE.search(text))

        def related(lab: frozenset) -> bool:
            return any(lab <= known or known <= lab for known in labels)

        reuse = None
        fresh = has_fresh_eval((sel.cell, max(sel.end_line, sel.line)), labels, sel.targets)
        for m in flow.calls:
            at = (m.cell, m.line)
            if at <= (sel.cell, max(sel.end_line, sel.line)) or not is_metric(m):
                continue
            _, binds = flow.chain(m.arg_names - label_names(m), at, mutations=True)
            lab = canonical(label_names(m), at)
            if lab and binds & selected and related(lab):
                reuse = reuse or at
        for at, reads in sorted(statements, key=lambda s: s[0]):
            if reuse is not None:
                break
            if len(at) == 3 and at <= (sel.cell, sel.line, sel.col):
                continue
            if len(at) == 2 and at <= (sel.cell, max(sel.end_line, sel.line)):
                continue
            hits = {n for n in reads if flow.binding(n, at) in selected}
            if not hits:
                continue
            if row_pick or any(
                flow.binding(n, at, mutations=True) in chain_binds and score_bearing(n, at) for n in reads - hits
            ):
                reuse = at
        if reuse is None:
            continue

        confidence = 0.9 if labels and not fresh else 0.6
        target = _join_names({t for t, _ in selected})
        evidence = (
            f"`{target}` (cell {sel.cell}) is chosen by comparing scores computed on the same rows "
            f"whose score is then reported for it (cell {reuse[0]})"
            + ("; a later evaluation on other rows exists (candidate)" if fresh else "")
        )
        flags.append(_make_flag(
            "leakage-test-selection", confidence=confidence, cell=sel.cell, line=sel.line,
            evidence=evidence, selected=sorted(t for t, _ in selected),
        ))
    seen: set[tuple[int, int]] = set()
    unique = []
    for f in flags:
        if (f.cell, f.line) not in seen:
            seen.add((f.cell, f.line))
            unique.append(f)
    flags = unique
    flagged_at = seen
    for mx in flow.calls:
        if mx.name not in MAX_CALLS or mx.receiver not in (None, "np", "numpy") or mx.kw_args:
            continue
        if len(mx.pos_args) != 1 or len(mx.pos_args[0]) != 1:
            continue
        at = (mx.cell, mx.line)
        if at in flagged_at:
            continue
        pool = next(iter(mx.pos_args[0]))
        events, _ = flow.chain({pool}, at, mutations=True)
        looped = [
            c for ev in events for c in calls_in(ev)
            if is_metric(c) and (c.loop_depth > 0 or LOOP_TEXT_RE.search(span_text(ev)))
        ]
        if not looped:
            continue
        loop_labels = {canonical(label_names(c), (c.cell, c.line)) for c in looped} - {frozenset()}
        if len(loop_labels) != 1:
            continue
        pool_bind = flow.binding(pool, at, mutations=True)
        reads_pool = {
            (c.cell, c.line) for c in flow.calls
            if pool in c.arg_names and flow.binding(pool, (c.cell, c.line), mutations=True) == pool_bind
        }
        if any(c.name in SUMMARY_CALLS and (c.cell, c.line) in reads_pool for c in flow.calls):
            continue
        own = next((ev for ev in flow.assigns if ev.call is mx), None)
        printed = any(c.name == "print" and (c.cell, c.line) == at for c in calls_by_cell.get(mx.cell, [])) and printed_directly(mx)
        if own is not None:
            mine = {(t, id(own)) for t in own.targets}
            printed = printed or any(
                c.name == "print" and (c.cell, c.line) > at
                and any(flow.binding(n, (c.cell, c.line)) in mine for n in c.arg_names)
                for c in flow.calls
            )
        if not printed:
            continue
        fresh = has_fresh_eval(at, loop_labels, None)
        flags.append(_make_flag(
            "leakage-test-selection", confidence=0.6 if fresh else 0.9, cell=mx.cell, line=mx.line,
            evidence=(
                f"`{mx.func}({pool})` (cell {mx.cell}) reports the best of scores computed in a loop "
                f"on the same rows, with no mean or spread across the candidates"
                + ("; a later evaluation on other rows exists (candidate)" if fresh else "")
            ),
            selected=[pool], shape="best-of-n",
        ))
        flagged_at.add(at)
    return flags


def detect_leakage_resample_before_split(nb: ParsedNotebook, flow: NotebookDataflow) -> list[Flag]:
    sinks = [c for c in flow.calls if c.name == "train_test_split" or c.name in CV_SINKS]
    if not sinks:
        return []
    sklearn_resample = bool(SKLEARN_RESAMPLE_RE.search(nb.full_source()))
    calls_by_cell: dict[int, list[CallSite]] = {}
    for c in flow.calls:
        calls_by_cell.setdefault(c.cell, []).append(c)

    def is_resample(c: CallSite) -> bool:
        if c.name in RESAMPLE_METHODS:
            return True
        if c.name == "resample":
            return c.receiver in {"utils", "sklearn.utils"} or (c.receiver is None and sklearn_resample)
        return c.name == "sample" and c.receiver is not None and c.kw_args.get("replace") == {"True"}

    flags: list[Flag] = []
    seen: set[int] = set()
    for s in sinks:
        if s.name in CV_SINKS:
            seed = set().union(
                set(), *s.pos_args[1:3],
                s.kw_args.get("X", set()), s.kw_args.get("y", set()),
            )
        else:
            seed = s.arg_names
        events, _ = flow.chain(seed, (s.cell, s.line))
        for ev in events:
            end = max(ev.end_line, ev.line)
            for c in calls_by_cell.get(ev.cell, []):
                if id(c) in seen or not ev.line <= c.line <= end or not is_resample(c):
                    continue
                seen.add(id(c))
                flags.append(_make_flag(
                    "leakage-resample-before-split", confidence=0.9, cell=c.cell, line=c.line,
                    evidence=(
                        f"`{c.func}(...)` adds resampled rows that reach `{s.name}` (cell {s.cell}); "
                        f"copies of one original row can land in both the training and the test part"
                    ),
                    sink=s.name, sink_cell=s.cell,
                ))
    return flags


DETECTORS = [
    detect_leakage_fit_before_split,
    detect_leakage_temporal_shuffle,
    detect_multiple_testing,
    detect_baserate_accuracy,
    detect_survivorship_candidate,
    detect_leakage_test_selection,
    detect_leakage_resample_before_split,
]

# flaw classes the static layer can decide on its own (measured by gate G1)
STATIC_DECIDABLE = {
    "leakage-fit-before-split",
    "leakage-temporal-shuffle",
    "testing-multiple-uncorrected",
    "baserate-accuracy-imbalanced",
    "leakage-test-selection",
    "leakage-resample-before-split",
}


def probe_arg(call) -> str:
    names = call.pos_args[0] if call.pos_args else call.kw_args.get("X", set())
    return next(iter(names)) if len(names) == 1 else ""


def run_static(nb: ParsedNotebook, flow: NotebookDataflow | None = None) -> list[Flag]:
    if flow is None:
        flow = analyze(nb)
    flags: list[Flag] = []
    for detector in DETECTORS:
        flags.extend(detector(nb, flow))
    return flags
