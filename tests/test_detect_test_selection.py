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


SCORED = (
    "P = {n: m.fit(X_tr, y_tr).predict_proba(X_te)[:, 1] for n, m in models.items()}\n"
    "res = pd.DataFrame({n: {'auc': roc_auc_score(y_te, p)} for n, p in P.items()}).T"
)


def test_ifelse_comparing_score_lookups_is_selection():
    cells = [SCORED, "best = 'lr' if res.loc['lr', 'auc'] >= res.loc['gb', 'auc'] else 'gb'", "print(res.loc[best])"]
    flags = confident(cells)
    assert len(flags) == 1 and flags[0].extra["selected"] == ["best"]


def test_ifelse_on_row_count_is_silent():
    cells = [SCORED, "best = 'lr' if len(X_tr) < 5000 else 'gb'", "print(res.loc[best])"]
    assert not selection_flags(cells)


def test_two_statements_on_selection_line_give_one_flag():
    cells = [FIT, "best = max(probs, key=lambda n: roc_auc_score(y_te, probs[n])); p = probs[best]",
             "print(average_precision_score(y_te, p))"]
    flags = confident(cells)
    assert len(flags) == 1 and flags[0].extra["selected"] == ["best"]


PROBS = "P = {n: m.fit(X_tr, y_tr).predict_proba(X_te)[:, 1] for n, m in models.items()}"


def test_values_alias_of_the_same_label_is_reuse():
    cells = [PROBS, "res = {n: roc_auc_score(y_te, p) for n, p in P.items()}\nbest = max(res, key=res.get)",
             "yt = y_te.values; pb = P[best]\nprint(roc_auc_score(yt, pb))"]
    assert confident(cells)


def test_values_alias_of_a_different_label_stays_candidate():
    cells = [
        "fitted = {n: m.fit(X_tr, y_tr) for n, m in models.items()}",
        "res = {n: roc_auc_score(y_va, f.predict_proba(X_va)[:, 1]) for n, f in fitted.items()}\n"
        "best = max(res, key=res.get)",
        "yt = y_te.values\nprint(roc_auc_score(yt, fitted[best].predict_proba(X_te)[:, 1]))",
    ]
    assert not confident(cells)


def test_wrapper_with_global_label_counts_as_reuse():
    cells = [
        "def evaluate(model):\n"
        "    p = cross_val_predict(model, X, y, cv=5, method='predict_proba')[:, 1]\n"
        "    return roc_auc_score(y, p), p",
        "out = {n: evaluate(m) for n, m in models.items()}\nbest = max(out, key=lambda n: out[n][0])",
        "print(roc_auc_score(y, out[best][1]))",
    ]
    assert confident(cells)


def test_wrapper_label_parameter_maps_to_call_argument():
    cells = [
        "def rep(name, yt, p):\n    return {'model': name, 'auc': roc_auc_score(yt, p)}",
        PROBS,
        "res = pd.DataFrame([rep(n, y_te, p) for n, p in P.items()]).set_index('model')\nbest = res['auc'].idxmax()",
        "print(rep(best, y_te, P[best]))",
    ]
    assert confident(cells)


def test_wrapper_then_fresh_test_rows_is_silent_or_candidate():
    cells = [
        "def evaluate(model):\n"
        "    p = cross_val_predict(model, X, y, cv=5, method='predict_proba')[:, 1]\n"
        "    return roc_auc_score(y, p), p",
        "out = {n: evaluate(m) for n, m in models.items()}\nbest = max(out, key=lambda n: out[n][0])",
        "print(roc_auc_score(y_test, models[best].fit(X, y).predict_proba(X_test)[:, 1]))",
    ]
    assert not confident(cells)


def test_wrapper_local_label_is_not_a_free_name():
    cells = [
        "yy = y_te.values",
        "def evaluate(model, p):\n    yy = y_va\n    return roc_auc_score(yy, p)",
        "res = {n: evaluate(n, p) for n, p in P.items()}\nbest = max(res, key=res.get)",
        "print(roc_auc_score(y_te, P[best]))",
    ]
    assert not confident(cells)


REP_DEF = "def rep(name, yt, p):\n    return {'model': name, 'auc': roc_auc_score(yt, p)}"


def test_wrapper_positional_label_from_validation_stays_candidate():
    cells = [
        REP_DEF,
        PROBS,
        "res = pd.DataFrame([rep(n, y_va, p) for n, p in P.items()]).set_index('model')\nbest = res['auc'].idxmax()",
        "print(rep(best, y_te, P[best]))",
    ]
    assert not confident(cells)


def test_wrapper_keyword_label_from_validation_stays_candidate():
    cells = [
        REP_DEF,
        PROBS,
        "res = pd.DataFrame([rep(n, yt=y_va, p=p) for n, p in P.items()]).set_index('model')\nbest = res['auc'].idxmax()",
        "print(rep(best, yt=y_te, p=P[best]))",
    ]
    assert not confident(cells)


def test_wrapper_keyword_label_reuse_is_confident():
    cells = [
        REP_DEF,
        PROBS,
        "res = pd.DataFrame([rep(n, yt=y_te, p=p) for n, p in P.items()]).set_index('model')\nbest = res['auc'].idxmax()",
        "print(rep(best, yt=y_te, p=P[best]))",
    ]
    assert confident(cells)
