import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold, StratifiedKFold, cross_val_predict

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261013


def z(x: np.ndarray) -> np.ndarray:
    return (x - x.mean()) / x.std()


def smooth_walk(rng: np.random.Generator, n: int, scale: float, window: int) -> np.ndarray:
    walk = np.cumsum(rng.normal(0, 1, n + window))
    smooth = np.convolve(walk, np.ones(window) / window, mode="valid")[:n]
    return scale * z(smooth)


def bernoulli(rng: np.random.Generator, logit: np.ndarray) -> np.ndarray:
    return (rng.random(len(logit)) < 1 / (1 + np.exp(-logit))).astype(int)


def maintenance(rng: np.random.Generator) -> tuple[pd.DataFrame, dict]:
    n, days = 6000, 730
    t = rng.uniform(0, days, n)
    risk = smooth_walk(rng, days, 1.6, 20)[t.astype(int)]
    vibration = rng.lognormal(0.5, 0.4, n)
    bearing = rng.normal(60, 8, n)
    load = rng.uniform(30, 100, n)
    site = rng.choice(list("ABCDE"), n)
    w = t / days
    logit = -3.2 + (1.3 - 1.2 * w) * z(vibration) + 0.5 * z(bearing) + (0.1 + 1.2 * w) * z(load) + risk
    failed = bernoulli(rng, logit)
    parts = np.where(failed == 1, rng.poisson(2.0, n) + 1, rng.binomial(1, 0.05, n))
    df = pd.DataFrame({
        "asset_tag": [f"AT-{i:05d}" for i in rng.permutation(n)],
        "inspected_at": (pd.Timestamp("2024-01-01") + pd.to_timedelta(t, unit="D")).strftime("%Y-%m-%d %H:%M"),
        "site": site,
        "vibration_rms": vibration.round(3),
        "bearing_temp_c": bearing.round(1),
        "ambient_temp_c": (12 + 10 * np.sin(2 * np.pi * t / 365) + rng.normal(0, 2, n)).round(1),
        "meter_hours": np.clip(2000 + 15 * t + rng.normal(0, 200, n), 0, None).round(0).astype(int),
        "load_pct": load.round(1),
        "parts_replaced": parts,
        "failed_90d": failed,
    })
    dictionary = {
        "asset_tag": "Identifier of the inspected asset.",
        "inspected_at": "Date and time of the inspection.",
        "site": "Plant where the asset is installed.",
        "vibration_rms": "RMS vibration measured during the inspection, mm/s.",
        "bearing_temp_c": "Bearing temperature measured during the inspection, Celsius.",
        "ambient_temp_c": "Ambient temperature at the site during the inspection, Celsius.",
        "meter_hours": "Operating hours on the asset's meter at the inspection.",
        "load_pct": "Average load over the week before the inspection, percent of rated load.",
        "parts_replaced": "Number of parts replaced on the work order that closed this inspection record.",
        "failed_90d": "1 if the asset failed within 90 days after the inspection, else 0.",
    }
    return df.sample(frac=1, random_state=SEED).reset_index(drop=True), dictionary


def clinic(rng: np.random.Generator) -> tuple[pd.DataFrame, dict]:
    patients = 1500
    visits = 1 + rng.poisson(7, patients)
    pid = np.repeat(np.arange(patients), visits)
    n = len(pid)
    effect = rng.normal(0, 2.5, patients)[pid]
    birth_year = rng.integers(1935, 2005, patients)[pid]
    sex = rng.choice(["F", "M"], patients)[pid]
    area = rng.integers(10, 60, patients)[pid]
    bmi = (rng.normal(27, 4, patients)[pid] + rng.normal(0, 0.05, n))
    los = rng.gamma(2.0, 2.0, n)
    meds = rng.poisson(6, n)
    lab_a = rng.normal(100, 15, n)
    lab_b = rng.normal(4.5, 0.6, n)
    visit_number = np.concatenate([np.arange(1, v + 1) for v in visits])
    logit = -2.7 + effect + 0.6 * z(los) + 0.5 * z(meds.astype(float)) + 0.5 * z(lab_a)
    keys = rng.choice(np.arange(100000, 1000000), patients, replace=False)
    df = pd.DataFrame({
        "person_key": keys[pid],
        "visit_number": visit_number,
        "birth_year": birth_year,
        "sex": sex,
        "postcode_area": area,
        "bmi": bmi.round(1),
        "length_of_stay_days": los.round(1),
        "n_medications": meds,
        "lab_a": lab_a.round(1),
        "lab_b": lab_b.round(2),
        "readmit_30d": bernoulli(rng, logit),
    })
    dictionary = {
        "person_key": "Pseudonymous key of the person.",
        "visit_number": "Sequence number of this hospital stay for the person.",
        "birth_year": "Year of birth.",
        "sex": "Recorded sex.",
        "postcode_area": "Numeric code of the residence area.",
        "bmi": "Body mass index recorded at admission.",
        "length_of_stay_days": "Length of this hospital stay in days.",
        "n_medications": "Number of medications at discharge.",
        "lab_a": "Result of lab test A at admission.",
        "lab_b": "Result of lab test B at admission.",
        "readmit_30d": "1 if the person was readmitted within 30 days after discharge, else 0.",
    }
    return df.sample(frac=1, random_state=SEED).reset_index(drop=True), dictionary


def subscriptions(rng: np.random.Generator) -> tuple[pd.DataFrame, dict]:
    accounts, months = 3000, 24
    drift = smooth_walk(rng, months, 1.2, 2)
    rows = []
    for a in range(accounts):
        start = int(rng.integers(0, months - 2))
        plan = rng.choice(["basic", "pro", "team"], p=[0.5, 0.35, 0.15])
        seats = 1 if plan == "basic" else int(rng.integers(2, 40))
        appetite = rng.normal(0, 1)
        churn_month = None
        history = []
        for m in range(start, months - 1):
            usage = max(0.0, 20 + 8 * appetite + rng.normal(0, 6))
            tickets = int(rng.poisson(0.6 + 0.4 * max(0.0, -appetite)))
            fee = {"basic": 12, "pro": 30, "team": 25 * seats}[plan] * (1.15 if m >= 12 else 1.0)
            logit = -3.0 - (0.10 - 0.004 * m) * (usage - 20) + (0.1 + 0.04 * m) * tickets + (0.8 if m >= 12 else 0.0) + drift[m]
            churned = int(rng.random() < 1 / (1 + np.exp(-logit)))
            history.append((m, m - start + 1, usage, tickets, fee, churned))
            if churned:
                churn_month = m + 1
                break
        lifetime = (churn_month if churn_month is not None else months) - start
        ref = f"C{a:05d}{int(rng.integers(10, 99))}"
        for m, tenure, usage, tickets, fee, churned in history:
            rows.append({
                "account_ref": ref,
                "snapshot_month": (pd.Timestamp("2024-01-01") + pd.DateOffset(months=m)).strftime("%Y-%m"),
                "plan": plan,
                "seats": seats,
                "monthly_fee": round(fee, 2),
                "tenure_months": tenure,
                "usage_hours": round(usage, 1),
                "support_tickets": tickets,
                "lifetime_months": lifetime,
                "churn_next_month": churned,
            })
    df = pd.DataFrame(rows)
    dictionary = {
        "account_ref": "Account identifier.",
        "snapshot_month": "Month of this monthly account snapshot.",
        "plan": "Subscription plan in the snapshot month.",
        "seats": "Number of paid seats.",
        "monthly_fee": "Fee billed for the snapshot month.",
        "tenure_months": "Months since the account started, counting the snapshot month.",
        "usage_hours": "Product usage in the snapshot month, hours.",
        "support_tickets": "Support tickets opened in the snapshot month.",
        "lifetime_months": "Total months the account was active, from the CRM export of 2026-01-05.",
        "churn_next_month": "1 if the account cancelled in the month after the snapshot month, else 0.",
    }
    return df.sample(frac=1, random_state=SEED).reset_index(drop=True), dictionary


def loans(rng: np.random.Generator) -> tuple[pd.DataFrame, dict]:
    n = 8000
    income = rng.lognormal(3.9, 0.45, n)
    debt = rng.beta(2, 5, n)
    lines = rng.poisson(4, n)
    age = rng.integers(21, 75, n)
    employment = np.clip(rng.normal(8, 6, n), 0, None)
    amount = rng.lognormal(2.6, 0.6, n)
    region = rng.choice(["north", "south", "east", "west"], n)
    logit = -2.6 - 0.5 * z(np.log(income)) + 0.8 * z(debt) + 0.4 * z(np.log(amount)) - 0.3 * z(employment)
    df = pd.DataFrame({
        "application_id": rng.choice(np.arange(10**6, 10**7), n, replace=False),
        "region": region,
        "income_k": income.round(1),
        "debt_ratio": debt.round(3),
        "credit_lines": lines,
        "age": age,
        "employment_years": employment.round(1),
        "loan_amount_k": amount.round(1),
        "defaulted": bernoulli(rng, logit),
    })
    dictionary = {
        "application_id": "Identifier of the loan application.",
        "region": "Region of the applicant.",
        "income_k": "Declared yearly income at application, thousands.",
        "debt_ratio": "Debt payments over income at application.",
        "credit_lines": "Open credit lines at application.",
        "age": "Applicant age at application.",
        "employment_years": "Years with the current employer at application.",
        "loan_amount_k": "Requested loan amount, thousands.",
        "defaulted": "1 if the loan defaulted within 12 months after funding, else 0.",
    }
    return df, dictionary


def numeric(df: pd.DataFrame, drop: list[str]) -> pd.DataFrame:
    X = df.drop(columns=drop)
    return pd.get_dummies(X, columns=list(X.select_dtypes(exclude="number").columns), dtype=float)


def oof_auc(X: pd.DataFrame, y: pd.Series, cv, groups=None, model=None) -> float:
    model = HistGradientBoostingClassifier(random_state=0) if model is None else model
    p = cross_val_predict(model, X, y, cv=cv, groups=groups, method="predict_proba")[:, 1]
    return round(float(roc_auc_score(y, p)), 3)


def forest() -> RandomForestClassifier:
    return RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=0)


def holdout_auc(X: pd.DataFrame, y: pd.Series, train: np.ndarray, test: np.ndarray) -> float:
    model = HistGradientBoostingClassifier(random_state=0).fit(X[train], y[train])
    return round(float(roc_auc_score(y[test], model.predict_proba(X[test])[:, 1])), 3)


def single_column_auc(x: pd.Series, y: pd.Series) -> float:
    auc = roc_auc_score(y, x)
    return round(float(max(auc, 1 - auc)), 3)


def trap_checks(name: str, df: pd.DataFrame) -> dict:
    kfold = StratifiedKFold(5, shuffle=True, random_state=0)
    if name == "maintenance":
        y = df["failed_90d"]
        t = pd.to_datetime(df["inspected_at"])
        X = numeric(df, ["asset_tag", "inspected_at", "parts_replaced", "failed_90d"]).assign(day=(t - t.min()).dt.days)
        late = (t >= t.quantile(0.75)).to_numpy()
        return {
            "positive_rate": round(float(y.mean()), 3),
            "auc_random_5fold": oof_auc(X, y, kfold),
            "auc_temporal_holdout_last_25pct": holdout_auc(X, y, ~late, late),
            "auc_temporal_holdout_with_parts_replaced": holdout_auc(
                X.assign(parts_replaced=df["parts_replaced"]), y, ~late, late),
            "single_column_auc_parts_replaced": single_column_auc(df["parts_replaced"], y),
        }
    if name == "clinic":
        y = df["readmit_30d"]
        X = numeric(df, ["person_key", "readmit_30d"])
        return {
            "positive_rate": round(float(y.mean()), 3),
            "rows_per_person_mean": round(len(df) / df["person_key"].nunique(), 2),
            "auc_row_5fold": oof_auc(X, y, kfold),
            "auc_group_5fold": oof_auc(X, y, GroupKFold(5), groups=df["person_key"]),
            "auc_row_5fold_random_forest": oof_auc(X, y, kfold, model=forest()),
            "auc_group_5fold_random_forest": oof_auc(X, y, GroupKFold(5), groups=df["person_key"], model=forest()),
        }
    if name == "subscriptions":
        y = df["churn_next_month"]
        month = df["snapshot_month"]
        late = (month >= sorted(month.unique())[-6]).to_numpy()
        X = numeric(df, ["account_ref", "snapshot_month", "lifetime_months", "churn_next_month"]).assign(
            month=pd.to_datetime(month).dt.month + 12 * pd.to_datetime(month).dt.year)
        return {
            "positive_rate": round(float(y.mean()), 3),
            "auc_random_5fold": oof_auc(X, y, kfold),
            "auc_temporal_holdout_last_6_months": holdout_auc(X, y, ~late, late),
            "auc_temporal_holdout_with_lifetime_months": holdout_auc(
                X.assign(lifetime_months=df["lifetime_months"]), y, ~late, late),
        }
    y = df["defaulted"]
    return {
        "positive_rate": round(float(y.mean()), 3),
        "auc_random_5fold": oof_auc(numeric(df, ["application_id", "defaulted"]), y, kfold),
    }


GENERATORS = {"maintenance": maintenance, "clinic": clinic, "subscriptions": subscriptions, "control": loans}


def main() -> int:
    p = argparse.ArgumentParser(prog="agent_baseline_v2_data")
    p.add_argument("--out", type=Path, default=ROOT / "scratch" / "agent-baseline-v2" / "data")
    args = p.parse_args()
    report = {}
    for i, (name, make) in enumerate(GENERATORS.items()):
        df, dictionary = make(np.random.default_rng(SEED + i))
        assert list(dictionary) == list(df.columns)
        folder = args.out / name
        folder.mkdir(parents=True, exist_ok=True)
        df.to_csv(folder / "data.csv", index=False)
        pd.DataFrame({"column": list(dictionary), "description": list(dictionary.values())}).to_csv(
            folder / "columns.csv", index=False)
        report[name] = {
            "rows": len(df),
            "csv_sha256": hashlib.sha256((folder / "data.csv").read_bytes()).hexdigest(),
            "columns_sha256": hashlib.sha256((folder / "columns.csv").read_bytes()).hexdigest(),
            "trap_check": trap_checks(name, df),
        }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
