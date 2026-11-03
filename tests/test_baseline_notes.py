from waldean.analysis.dataflow import analyze
from waldean.checks.detect import baseline_notes

from test_detect import nb

FIT = "model.fit(X_tr, y_tr)\np = model.predict_proba(X_te)[:, 1]\nprint(roc_auc_score(y_te, p))"


def notes(cells):
    notebook = nb(cells)
    return baseline_notes(notebook, analyze(notebook))


def test_classification_metric_without_baseline_gets_note():
    out = notes([("code", FIT)])
    assert len(out) == 1
    assert "`roc_auc_score` (cell 0)" in out[0]
    assert "DummyClassifier" in out[0]


def test_regression_note_names_persistence():
    out = notes([("code", "model.fit(X_tr, y_tr)\nprint(mean_absolute_error(y_te, model.predict(X_te)))")])
    assert len(out) == 1
    assert "DummyRegressor" in out[0] and "last observed value" in out[0]


def test_no_note_with_dummy_classifier():
    cells = [("code", FIT), ("code", "dummy = DummyClassifier(strategy='most_frequent').fit(X_tr, y_tr)")]
    assert notes(cells) == []


def test_no_note_with_named_baseline_variable():
    cells = [("code", FIT), ("code", "baseline_auc = roc_auc_score(y_te, np.full(len(y_te), y_tr.mean()))")]
    assert notes(cells) == []


def test_no_note_with_markdown_base_rate():
    cells = [("code", FIT), ("markdown", "A majority-class predictor scores about 90% here.")]
    assert notes(cells) == []


def test_naive_bayes_import_is_not_a_baseline():
    cells = [("code", "from sklearn.naive_bayes import GaussianNB"), ("code", FIT)]
    assert len(notes(cells)) == 1


def test_no_note_without_metric():
    assert notes([("code", "stat, p = ttest_ind(a, b)\nprint(p)")]) == []


def test_note_points_at_first_metric_by_position():
    cells = [("code", "print('setup')"), ("code", FIT), ("code", "print(f1_score(y_te, p > 0.5))")]
    assert "`roc_auc_score` (cell 1)" in notes(cells)[0]
