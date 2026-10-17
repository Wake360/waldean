from waldean.analysis.dataflow import analyze
from waldean.checks.detect import detect_leakage_resample_before_split

from test_detect import nb

SPLIT = "X = df[cols]\ny = df['fraud']\nX_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25)"


def flags(cells):
    notebook = nb([("code", c) for c in cells])
    return detect_leakage_resample_before_split(notebook, analyze(notebook))


def test_sklearn_resample_before_split():
    cells = [
        "from sklearn.utils import resample\n"
        "minority = df[df.fraud == 1]\n"
        "df = pd.concat([df[df.fraud == 0], resample(minority, replace=True, n_samples=2700, random_state=0)])",
        SPLIT,
    ]
    out = flags(cells)
    assert [(f.cell, f.line, f.confidence) for f in out] == [(0, 3, 0.9)]
    assert out[0].extra == {"sink": "train_test_split", "sink_cell": 1}


def test_smote_fit_resample_before_split():
    cells = [
        "X_res, y_res = SMOTE(random_state=0).fit_resample(X, y)",
        "X_tr, X_te, y_tr, y_te = train_test_split(X_res, y_res, test_size=0.25)",
    ]
    assert len(flags(cells)) == 1


def test_pandas_sample_with_replace_before_split():
    cells = [
        "minority = df[df.fraud == 1]\n"
        "df = pd.concat([df, minority.sample(n=1200, replace=True, random_state=0)])",
        SPLIT,
    ]
    assert len(flags(cells)) == 1


def test_cross_validation_on_resampled_training_rows():
    cells = [
        "X_tr, X_te, y_tr, y_te = train_test_split(X, y)",
        "X_res, y_res = SMOTE().fit_resample(X_tr, y_tr)\nprint(cross_val_score(clf, X_res, y_res, cv=5))",
    ]
    out = flags(cells)
    assert len(out) == 1
    assert out[0].extra["sink"] == "cross_val_score"


def test_resample_after_split_on_training_rows_is_silent():
    cells = [
        "X_tr, X_te, y_tr, y_te = train_test_split(X, y)",
        "X_res, y_res = SMOTE().fit_resample(X_tr, y_tr)\nclf.fit(X_res, y_res)\n"
        "print(roc_auc_score(y_te, clf.predict_proba(X_te)[:, 1]))",
    ]
    assert not flags(cells)


def test_bootstrap_of_test_predictions_is_silent():
    cells = [
        SPLIT,
        "from sklearn.utils import resample\naucs = []\nfor i in range(200):\n"
        "    idx = resample(np.arange(len(y_te)), random_state=i)\n"
        "    aucs.append(roc_auc_score(y_te.iloc[idx], p[idx]))",
    ]
    assert not flags(cells)


def test_pandas_time_resample_is_silent():
    assert not flags(["df = df.set_index('date').resample('W').sum()", SPLIT])


def test_scipy_signal_resample_is_silent():
    assert not flags(["from scipy.signal import resample\ndf['x'] = resample(df['x'], len(df))", SPLIT])


def test_sampler_inside_imblearn_pipeline_is_silent():
    assert not flags(["pipe = make_pipeline(SMOTE(), LogisticRegression())\nprint(cross_val_score(pipe, X, y, cv=5))"])


def test_pandas_sample_without_replace_is_silent():
    assert not flags(["df = df.sample(frac=1.0, random_state=0)", SPLIT])


def test_random_undersampler_before_split_is_silent():
    assert not flags(["X, y = NearMiss().fit_resample(X, y)", SPLIT])
    assert not flags(["X, y = RandomUnderSampler(random_state=0).fit_resample(X, y)", SPLIT])
    assert not flags(["rus = RandomUnderSampler(random_state=0)\nX, y = rus.fit_resample(X, y)", SPLIT])


def test_resample_without_replace_before_split_is_silent():
    cells = [
        "from sklearn.utils import resample\n"
        "df = pd.concat([resample(maj, replace=False, n_samples=len(mino)), mino])",
        SPLIT,
    ]
    assert not flags(cells)


def test_smote_tomek_before_split_is_still_flagged():
    cells = [
        "X_res, y_res = SMOTETomek().fit_resample(X, y)",
        "X_tr, X_te, y_tr, y_te = train_test_split(X_res, y_res, test_size=0.25)",
    ]
    assert len(flags(cells)) == 1


def test_project_utils_resample_is_silent():
    assert not flags(["import utils\ndf['x'] = utils.resample(df['x'], '1D')", SPLIT])
