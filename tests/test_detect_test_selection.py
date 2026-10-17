from waldean.analysis.dataflow import analyze
from waldean.checks.detect import detect_leakage_test_selection

from test_detect import nb

FIT = (
    "rows = []\n"
    "probs = {}\n"
    "for name, m in models.items():\n"
    "    m.fit(X_tr, y_tr)\n"
    "    p = m.predict_proba(X_te)[:, 1]\n"
    "    probs[name] = p\n"
    "    rows.append({'model': name, 'auc': roc_auc_score(y_te, p)})\n"
    "res = pd.DataFrame(rows).set_index('model')"
)


def selection_flags(cells):
    notebook = nb([("code", c) for c in cells])
    return detect_leakage_test_selection(notebook, analyze(notebook))


def confident(cells):
    return [f for f in selection_flags(cells) if f.confidence >= 0.8]


def test_idxmax_on_test_scores_then_reported():
    flags = confident([FIT, "best = res['auc'].idxmax()", "print(roc_auc_score(y_te, probs[best]))"])
    assert len(flags) == 1
    assert flags[0].extra["selected"] == ["best"]


def test_sorted_table_first_row_then_lookup():
    cells = [FIT, "res = res.sort_values('auc', ascending=False)\nbest = res.index[0]", "print(res.loc[best])"]
    assert confident(cells)


def test_max_with_key_lambda_on_same_line_reuse():
    cells = [FIT, "best = max(probs, key=lambda n: roc_auc_score(y_te, probs[n])); p = probs[best]",
             "print(average_precision_score(y_te, p))"]
    assert confident(cells)


def test_threshold_tuned_and_reported_on_test():
    cells = [
        "p = model.predict_proba(X_te)[:, 1]\nprec, rec, thr = precision_recall_curve(y_te, p)",
        "f1 = 2 * prec * rec / (prec + rec)\ni = np.argmax(f1[:-1])\nt = thr[i]",
        "print(f1_score(y_te, p >= t))",
    ]
    assert confident(cells)


def test_validation_selection_with_fresh_test_is_only_a_candidate():
    cells = [
        FIT.replace("X_te", "X_va").replace("y_te", "y_va"),
        "best = res['auc'].idxmax()\nprint(res.loc[best])",
        "print(roc_auc_score(y_test, models[best].predict_proba(X_test)[:, 1]))",
    ]
    flags = selection_flags(cells)
    assert flags and all(f.confidence < 0.8 for f in flags)


def test_selection_without_reuse_is_silent():
    cells = [FIT, "best = res['auc'].idxmax()", "final = models[best].fit(X_all, y_all)"]
    assert not selection_flags(cells)


def test_unsorted_first_row_lookup_is_silent():
    cells = [FIT, "a = res.query(\"model == 'lr'\").iloc[0]", "print(a)"]
    assert not selection_flags(cells)


def test_argmax_without_scores_is_silent():
    cells = ["counts = df.groupby('city').size()", "top = counts.idxmax()", "print(df[df.city == top].price.mean())"]
    assert not selection_flags(cells)


def test_user_metric_function_counts_as_scoring():
    cells = [
        "def score(y, p):\n    return {'auc': roc_auc_score(y, p)}",
        "oof = {n: cross_val_predict(m, X, y, cv=cv, method='predict_proba')[:, 1] for n, m in models.items()}",
        "results = pd.DataFrame({n: score(y, p) for n, p in oof.items()}).T.sort_values('auc', ascending=False)",
        "best = results.index[0]\nprint(score(y, oof[best]))",
    ]
    assert confident(cells)


def test_first_index_meeting_a_condition_is_silent():
    cells = [
        "y_scores = cross_val_predict(clf, X, y, cv=3, method='decision_function')\n"
        "prec, rec, thr = precision_recall_curve(y, y_scores)",
        "idx = (prec >= 0.90).argmax()\nt = thr[idx]",
        "print(recall_score(y, y_scores >= t))",
    ]
    assert not selection_flags(cells)


def test_threshold_tuned_on_oof_recorded_with_choice_then_fresh_test_is_silent():
    cells = [
        "rows = []\noof = {}\nfor name, m in models.items():\n"
        "    p = cross_val_predict(m, X_tr, y_tr, cv=folds, method='predict_proba')[:, 1]\n"
        "    oof[name] = p\n"
        "    rows.append((name, roc_auc_score(y_tr, p)))\n"
        "cvres = pd.DataFrame(rows, columns=['model', 'cv_auc']).set_index('model')",
        "best = cvres.cv_auc.idxmax()\np = oof[best]\nths = np.linspace(0.05, 0.6, 111)\n"
        "f1 = [f1_score(y_tr, p >= t) for t in ths]\nthr = float(ths[int(np.argmax(f1))])\n"
        "choice = {'model': best, 'threshold': round(thr, 3)}\nprint(json.dumps(choice))",
        "final = models[best].fit(X_tr, y_tr)\npt = final.predict_proba(X_te)[:, 1]\n"
        "print(roc_auc_score(y_te, pt), f1_score(y_te, pt >= thr))",
    ]
    assert not confident(cells)


SEED_LOOP = (
    "seed_aucs = []\n"
    "for s in range(20):\n"
    "    rf = RandomForestClassifier(random_state=s).fit(X_tr, y_tr)\n"
    "    seed_aucs.append(roc_auc_score(y_te, rf.predict_proba(X_te)[:, 1]))"
)


def test_max_over_seed_scores_printed():
    flags = confident([SEED_LOOP, "best_auc = max(seed_aucs)\nprint(f'forest test roc_auc={best_auc:.3f}')"])
    assert len(flags) == 1
    assert flags[0].extra == {"selected": ["seed_aucs"], "shape": "best-of-n"}
    assert (flags[0].cell, flags[0].line) == (1, 1)


def test_np_max_over_comprehension_scores_printed():
    cells = [
        "aucs = [roc_auc_score(y_te, RandomForestClassifier(random_state=s).fit(X_tr, y_tr)"
        ".predict_proba(X_te)[:, 1]) for s in range(20)]",
        "print('auc', np.max(aucs))",
    ]
    assert [f.extra["shape"] for f in confident(cells)] == ["best-of-n"]


def test_best_of_n_with_mean_reported_is_silent():
    assert not selection_flags([SEED_LOOP, "print(np.mean(seed_aucs), np.std(seed_aucs), max(seed_aucs))"])


def test_best_of_n_with_series_mean_is_silent():
    cells = [SEED_LOOP, "print(pd.Series(seed_aucs).mean())\nprint(max(seed_aucs))"]
    assert not selection_flags(cells)


def test_best_of_n_not_reported_is_silent():
    assert not selection_flags([SEED_LOOP, "plt.ylim(0, max(seed_aucs))"])


def test_max_over_non_metric_values_is_silent():
    cells = [
        "losses = []\nfor s in range(20):\n    losses.append(train_one(s))",
        "print(max(losses))\nprint(max(df['price']))",
    ]
    assert not selection_flags(cells)


def test_dict_key_shape_still_one_flag():
    cells = [
        "res = {}\nfor s in range(20):\n    m = RandomForestClassifier(random_state=s).fit(X_tr, y_tr)\n"
        "    res[s] = roc_auc_score(y_te, m.predict_proba(X_te)[:, 1])",
        "best = max(res, key=res.get)\nprint(res[best])",
    ]
    flags = confident(cells)
    assert len(flags) == 1
    assert "shape" not in flags[0].extra


def test_mixed_label_pool_is_silent():
    cells = [
        "aucs = []\nfor m in models:\n"
        "    aucs.append(roc_auc_score(y_va, m.predict_proba(X_va)[:, 1]))\n"
        "    aucs.append(roc_auc_score(y_te, m.predict_proba(X_te)[:, 1]))",
        "print(max(aucs))",
    ]
    assert not selection_flags(cells)


def test_val_max_then_fresh_test_eval_is_candidate_only():
    cells = [
        "va = []\nfor c in [0.1, 1, 10]:\n"
        "    m = LogisticRegression(C=c).fit(X_tr, y_tr)\n"
        "    va.append(roc_auc_score(y_va, m.predict_proba(X_va)[:, 1]))",
        "print('best val', max(va))",
        "final = LogisticRegression().fit(X_tr, y_tr)\n"
        "print(roc_auc_score(y_te, final.predict_proba(X_te)[:, 1]))",
    ]
    flags = selection_flags(cells)
    assert not confident(cells)
    assert [f.confidence for f in flags] == [0.6]


def test_best_of_n_index_of_max_printed_is_silent():
    cells = [SEED_LOOP, "print('best seed', seed_aucs.index(max(seed_aucs)) + 1)"]
    assert not selection_flags(cells)


def test_best_of_n_comparison_printed_is_silent():
    assert not selection_flags([SEED_LOOP, "print(max(seed_aucs) > 0.9)"])


def test_best_of_n_two_maxes_on_one_line_flags_once():
    cells = [SEED_LOOP, "print('max', max(seed_aucs), 'seed', seed_aucs.index(max(seed_aucs)) + 1)"]
    assert len(confident(cells)) == 1
