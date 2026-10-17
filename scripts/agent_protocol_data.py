import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, StratifiedKFold

from agent_baseline_v2_data import (bernoulli, forest, holdout_auc, numeric, oof_auc, single_column_auc,
                                    smooth_walk, z)

ROOT = Path(__file__).resolve().parent.parent
SEED = 20261020


def shipments(rng: np.random.Generator):
    n, days, future_days = 9000, 730, 90
    total = days + future_days
    t = rng.uniform(0, total, n)
    trend = smooth_walk(rng, total, 1.5, 25)[t.astype(int)]
    distance = rng.lognormal(5.5, 0.6, n)
    weight = rng.lognormal(2.0, 0.8, n)
    carrier = rng.choice(["north", "coastal", "express"], n, p=[0.5, 0.3, 0.2])
    w = t / total
    logit = (-2.4 + (1.2 - 1.0 * w) * z(np.log(distance)) + (0.2 + 1.0 * w) * z(np.log(weight))
             + 0.6 * (carrier == "coastal") + trend)
    late = bernoulli(rng, logit)
    claim = np.where(late == 1, rng.gamma(2.0, 40.0, n), rng.binomial(1, 0.03, n) * rng.gamma(2.0, 20.0, n))
    df = pd.DataFrame({
        "consignment": [f"CN{i:06d}" for i in rng.permutation(n)],
        "dispatched_on": (pd.Timestamp("2024-03-01") + pd.to_timedelta(t, unit="D")).strftime("%Y-%m-%d %H:%M"),
        "carrier": carrier,
        "distance_km": distance.round(0).astype(int),
        "weight_kg": weight.round(2),
        "parcels": 1 + rng.poisson(1.5, n),
        "claim_paid_eur": claim.round(2),
        "late_delivery": late,
    })
    dictionary = {
        "consignment": "Identifier of the consignment.",
        "dispatched_on": "Date and time the consignment left the depot.",
        "carrier": "Carrier that handled the consignment.",
        "distance_km": "Road distance from depot to recipient, km.",
        "weight_kg": "Total weight of the consignment, kg.",
        "parcels": "Number of parcels in the consignment.",
        "claim_paid_eur": "Compensation paid on the customer claim settled for this consignment, euros.",
        "late_delivery": "1 if the consignment was delivered after the promised date, else 0.",
    }
    return df, t >= days, dictionary


def tutoring(rng: np.random.Generator):
    students, extra = 1800, 400
    people = students + extra
    sid = np.repeat(np.arange(people), 1 + rng.poisson(6, people))
    n = len(sid)
    ability = rng.normal(0, 2.2, people)[sid]
    minutes = rng.gamma(3.0, 15.0, n)
    hints = rng.poisson(2.0, n)
    passed = bernoulli(rng, -0.6 + ability + 0.5 * z(minutes) - 0.4 * z(hints))
    keys = np.array([f"S{k:05d}" for k in rng.permutation(people)])
    df = pd.DataFrame({
        "student_key": keys[sid],
        "enrol_year": rng.integers(2015, 2024, people)[sid],
        "school_code": rng.integers(100, 160, people)[sid],
        "prior_score": (rng.normal(60, 12, people)[sid] + rng.normal(0, 0.3, n)).round(2),
        "session_minutes": minutes.round(1),
        "hints_used": hints,
        "passed_quiz": passed,
    })
    dictionary = {
        "student_key": "Pseudonymous key of the student.",
        "enrol_year": "Year the student enrolled.",
        "school_code": "Code of the student's school.",
        "prior_score": "Score on the placement test, as stored on the session record.",
        "session_minutes": "Length of the tutoring session, minutes.",
        "hints_used": "Hints the student opened during the session.",
        "passed_quiz": "1 if the student passed the quiz that closed the session, else 0.",
    }
    return df, sid >= students, dictionary


def meters(rng: np.random.Generator):
    homes, months, future_months = 1500, 30, 6
    total = months + future_months
    drift = smooth_walk(rng, total, 1.0, 3)
    rows = []
    for h in range(homes):
        start = int(rng.integers(0, total - 3))
        tariff = str(rng.choice(["fixed", "variable", "prepay"], p=[0.5, 0.4, 0.1]))
        occupants = int(rng.integers(1, 6))
        thrift = rng.normal(0, 1)
        ref = f"M{h:05d}{int(rng.integers(10, 99))}"
        for m in range(start, total):
            kwh = max(0.0, 250 + 60 * occupants - 40 * thrift + rng.normal(0, 40))
            bill = kwh * (0.28 if tariff == "fixed" else 0.24 + 0.08 * (m >= 18))
            late_payments = int(rng.poisson(0.3 + 0.3 * max(0.0, -thrift)))
            logit = (-3.4 + (0.004 + 0.0002 * m) * (bill - 120) + (0.3 + 0.03 * m) * late_payments
                     - 0.6 * thrift + drift[m])
            arrears = int(rng.random() < 1 / (1 + np.exp(-logit)))
            notice = int((arrears and rng.random() < 0.9) or rng.random() < 0.02)
            rows.append({
                "meter_ref": ref,
                "billing_month": (pd.Timestamp("2023-07-01") + pd.DateOffset(months=m)).strftime("%Y-%m-%d"),
                "tariff": tariff,
                "occupants": occupants,
                "kwh": round(kwh, 1),
                "bill_eur": round(bill, 2),
                "late_payments_12m": late_payments,
                "final_notice_sent": notice,
                "arrears_next_month": arrears,
                "month_index": m,
            })
    df = pd.DataFrame(rows)
    future = (df["month_index"] >= months).to_numpy()
    df = df.drop(columns="month_index")
    dictionary = {
        "meter_ref": "Account identifier of the metered home.",
        "billing_month": "First day of the billing month of this row.",
        "tariff": "Tariff in the billing month.",
        "occupants": "Occupants declared on the account.",
        "kwh": "Electricity used in the billing month, kWh.",
        "bill_eur": "Amount billed for the billing month, euros.",
        "late_payments_12m": "Late payments on the account in the 12 months up to the billing month.",
        "final_notice_sent": "1 if the account was sent a final payment notice in the billing cycle that followed, else 0.",
        "arrears_next_month": "1 if the account was in arrears in the month after the billing month, else 0.",
    }
    return df, future, dictionary


def warranty(rng: np.random.Generator):
    n, future_n = 7000, 2000
    total = n + future_n
    age = rng.uniform(0, 5, total)
    price = rng.lognormal(5.5, 0.7, total)
    usage = rng.gamma(2.0, 3.0, total)
    channel = rng.choice(["store", "online", "partner"], total)
    logit = -2.3 + 0.6 * z(age) + 0.4 * z(np.log(price)) + 0.5 * z(usage) + 0.3 * (channel == "partner")
    df = pd.DataFrame({
        "device_serial": rng.choice(np.arange(10**7, 10**8), total, replace=False).astype(str),
        "channel": channel,
        "device_age_years": age.round(2),
        "price_eur": price.round(2),
        "daily_hours": usage.round(1),
        "claim_within_year": bernoulli(rng, logit),
    })
    dictionary = {
        "device_serial": "Serial number identifier of the device.",
        "channel": "Sales channel of the warranty.",
        "device_age_years": "Device age when the warranty was sold, years.",
        "price_eur": "Device price, euros.",
        "daily_hours": "Average daily use reported at registration, hours.",
        "claim_within_year": "1 if a warranty claim was filed within a year after the sale, else 0.",
    }
    return df, np.arange(total) >= n, dictionary


GENERATORS = {"shipments": shipments, "tutoring": tutoring, "meters": meters, "warranty": warranty}

SPECS = {
    "shipments": {"target": "late_delivery", "time": "dispatched_on", "group": None, "leak": "claim_paid_eur",
                  "ids": ["consignment"]},
    "tutoring": {"target": "passed_quiz", "time": None, "group": "student_key", "leak": None, "ids": []},
    "meters": {"target": "arrears_next_month", "time": "billing_month", "group": None, "leak": "final_notice_sent",
               "ids": ["meter_ref"]},
    "warranty": {"target": "claim_within_year", "time": None, "group": None, "leak": None, "ids": ["device_serial"]},
}


def trap_checks(spec: dict, df: pd.DataFrame) -> dict:
    y = df[spec["target"]]
    drop = [spec["target"], *spec["ids"], *(c for c in (spec["time"], spec["group"], spec["leak"]) if c)]
    X = numeric(df, drop)
    kfold = StratifiedKFold(5, shuffle=True, random_state=0)
    out = {"positive_rate": round(float(y.mean()), 3)}
    if spec["time"]:
        t = pd.to_datetime(df[spec["time"]])
        X = X.assign(day=(t - t.min()).dt.days)
        late = (t >= t.quantile(0.75)).to_numpy()
        out["auc_temporal_holdout_last_25pct"] = holdout_auc(X, y, ~late, late)
        if spec["leak"]:
            out["auc_temporal_holdout_with_leak"] = holdout_auc(X.assign(leak=df[spec["leak"]]), y, ~late, late)
    out["auc_random_5fold"] = oof_auc(X, y, kfold)
    if spec["group"]:
        out["auc_row_5fold_random_forest"] = oof_auc(X, y, kfold, model=forest())
        out["auc_group_5fold_random_forest"] = oof_auc(X, y, GroupKFold(5), groups=df[spec["group"]], model=forest())
    if spec["leak"]:
        out["single_column_auc_leak"] = single_column_auc(df[spec["leak"]], y)
    return out


def trap_failures(spec: dict, c: dict) -> list[str]:
    bad = []
    if spec["time"] and c["auc_random_5fold"] - c["auc_temporal_holdout_last_25pct"] < 0.03:
        bad.append("temporal")
    if spec["group"] and c["auc_row_5fold_random_forest"] - c["auc_group_5fold_random_forest"] < 0.03:
        bad.append("group")
    if spec["leak"] and c["auc_temporal_holdout_with_leak"] - c["auc_temporal_holdout_last_25pct"] < 0.1:
        bad.append("leak")
    return bad


def main() -> int:
    p = argparse.ArgumentParser(prog="agent_protocol_data")
    p.add_argument("--out", type=Path, default=ROOT / "scratch" / "agent-protocol" / "data")
    args = p.parse_args()
    report, failed = {}, False
    for i, (name, make) in enumerate(GENERATORS.items()):
        df, future, dictionary = make(np.random.default_rng(SEED + i))
        assert list(dictionary) == list(df.columns)
        past = df[~future].sample(frac=1, random_state=SEED).reset_index(drop=True)
        folder = args.out / name
        folder.mkdir(parents=True, exist_ok=True)
        past.to_csv(folder / "data.csv", index=False)
        df[future].reset_index(drop=True).to_csv(folder / "future.csv", index=False)
        pd.DataFrame({"column": list(dictionary), "description": list(dictionary.values())}).to_csv(
            folder / "columns.csv", index=False)
        checks = trap_checks(SPECS[name], past)
        bad = trap_failures(SPECS[name], checks)
        failed = failed or bool(bad)
        report[name] = {
            "rows": len(past),
            "future_rows": int(future.sum()),
            "csv_sha256": hashlib.sha256((folder / "data.csv").read_bytes()).hexdigest(),
            "columns_sha256": hashlib.sha256((folder / "columns.csv").read_bytes()).hexdigest(),
            "trap_check": checks,
            "trap_failures": bad,
        }
    print(json.dumps(report, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
