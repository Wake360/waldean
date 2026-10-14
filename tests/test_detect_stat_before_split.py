from waldean.checks.detect import run_static

from test_detect import nb

SPLIT = "X_tr, X_te, y_tr, y_te = train_test_split(df[feats], df.y)"
CV = "scores = cross_val_score(model, df[feats], df.y, cv=5)"


def leak_flags(cells, floor=0.8):
    notebook = nb([("code", c) for c in cells])
    return [f for f in run_static(notebook) if f.flaw_id == "leakage-fit-before-split" and f.confidence >= floor]


def test_hand_zscore_column_before_split():
    flags = leak_flags(["df = pd.read_csv('x.csv')", "df['a'] = (df['a'] - df['a'].mean()) / df['a'].std()", SPLIT])
    assert len(flags) == 1
    assert flags[0].extra["leaked_names"] == ["df"]


def test_divide_by_max_attribute_column_before_split():
    assert leak_flags(["df = pd.read_csv('x.csv')", "df.b = df.b / df.b.max()", SPLIT])


def test_groupby_transform_median_before_split():
    cells = [
        "df = pd.read_csv('x.csv')",
        "df['c'] = df.groupby('g')['c'].transform(lambda s: s.fillna(s.median()))",
        SPLIT,
    ]
    assert leak_flags(cells)


def test_groupby_transform_string_stat_before_split():
    assert leak_flags(["df = pd.read_csv('x.csv')", "df['d'] = df.groupby('g')['d'].transform('mean')", SPLIT])


def test_whole_frame_minmax_rebind_before_split():
    cells = ["X = df[feats]", "X = (X - X.min()) / (X.max() - X.min())", "X_tr, X_te, y_tr, y_te = train_test_split(X, df.y)"]
    assert leak_flags(cells)


def test_one_flag_per_frame():
    cells = [
        "df = pd.read_csv('x.csv')",
        "df['a'] = (df['a'] - df['a'].mean()) / df['a'].std()\ndf['b'] = df['b'].fillna(df['b'].median())",
        SPLIT,
    ]
    assert len(leak_flags(cells)) == 1


def test_stat_before_cv_is_candidate():
    flags = leak_flags(["df = pd.read_csv('x.csv')", "df['a'] = df['a'] / df['a'].max()", CV], floor=0.0)
    assert flags and all(f.confidence < 0.8 for f in flags)


def test_quantile_row_filter_is_silent():
    assert not leak_flags(["df = pd.read_csv('x.csv')", "df = df[df.p < df.p.quantile(0.99)]", SPLIT])


def test_eda_statistic_not_written_back_is_silent():
    assert not leak_flags(["df = pd.read_csv('x.csv')", "mu = df['a'].mean()\nprint(mu)", SPLIT])


def test_statistic_from_train_split_is_silent():
    cells = [
        "df = pd.read_csv('x.csv')",
        SPLIT,
        "mu, sd = X_tr['a'].mean(), X_tr['a'].std()\nX_tr['a'] = (X_tr['a'] - mu) / sd\nX_te['a'] = (X_te['a'] - mu) / sd",
    ]
    assert not leak_flags(cells)


def test_frame_rebuilt_after_statistic_is_silent():
    cells = ["df = pd.read_csv('x.csv')", "df['a'] = df['a'] / df['a'].max()", "df = pd.read_csv('other.csv')", SPLIT]
    assert not leak_flags(cells)


def test_rolling_window_mean_is_silent():
    cells = ["df = pd.read_csv('x.csv')", "df['ma'] = df['demand'].rolling(7).mean()", SPLIT]
    assert not leak_flags(cells)


def test_assign_with_frame_statistic_before_split():
    assert leak_flags(["df = pd.read_csv('x.csv')", "df = df.assign(a=df['a'] / df['a'].max())", SPLIT])


def test_chained_fillna_with_frame_mean_before_split():
    assert leak_flags(["df = pd.read_csv('x.csv')", "df = df.fillna(df.mean())", SPLIT])


def test_chained_pipe_of_lambda_statistic_before_split():
    assert leak_flags(["df = pd.read_csv('x.csv')", "df = df.pipe(lambda d: (d - d.mean()) / d.std())", SPLIT])


def test_rolling_on_full_frame_then_shuffled_split_is_temporal():
    notebook = nb([
        ("code", "df = pd.read_csv('x.csv', parse_dates=['date']).sort_values('date')"),
        ("code", "df['r7'] = df['y'].rolling(7).mean()"),
        ("code", "X_tr, X_te, y_tr, y_te = train_test_split(df[['r7']], df.y)"),
    ])
    assert "leakage-temporal-shuffle" in {f.flaw_id for f in run_static(notebook) if f.confidence >= 0.8}
