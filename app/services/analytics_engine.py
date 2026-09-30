"""
Structured analytics engine derived from the offline pandas main.py pipeline.

Returns JSON-serialisable dicts for FastAPI endpoints.
Loads from data/csv relative to the project root (cwd when uvicorn runs).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

DATA_DIR = Path("data/csv")


def _csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        # fallback if started from parent folder
        alt = Path("Kaushal trace backend") / "data" / "csv" / name
        path = alt if alt.exists() else path
    return pd.read_csv(path)


@lru_cache(maxsize=1)
def load_tables() -> Dict[str, pd.DataFrame]:
    return {
        "trainees": _csv("trainees.csv"),
        "training_records": _csv("training_records.csv"),
        "outcome_claims": _csv("outcome_claims.csv"),
        "evidence_records": _csv("evidence_records.csv"),
        "verification_records": _csv("verification_records.csv"),
        "employment_records": _csv("employment_records.csv"),
        "wage_records": _csv("wage_records.csv"),
        "followups": _csv("followups.csv"),
        "transitions": _csv("transitions.csv"),
        "employers": _csv("employers.csv"),
        "providers": _csv("providers.csv"),
        "courses": _csv("courses.csv"),
    }


def build_analytical_dataset() -> pd.DataFrame:
    t = load_tables()

    df = t["trainees"].merge(
        t["training_records"], on="trainee_id", how="left", suffixes=("", "_training")
    )
    df = df.merge(t["courses"], on="course_id", how="left", suffixes=("", "_course"))
    df = df.merge(t["providers"], on="provider_id", how="left", suffixes=("", "_provider"))
    df = df.merge(
        t["outcome_claims"],
        on=["trainee_id", "training_id"],
        how="left",
        suffixes=("", "_claim"),
    )

    ver = t["verification_records"].copy()
    ver["verified_at"] = pd.to_datetime(ver["verified_at"], errors="coerce")
    ver = ver.sort_values("verified_at").drop_duplicates(subset=["claim_id"], keep="last")
    df = df.merge(ver, on="claim_id", how="left", suffixes=("", "_verification"))

    evidence_summary = (
        t["evidence_records"]
        .groupby("claim_id")
        .agg(
            evidence_count=("evidence_id", "count"),
            supporting_evidence=("evidence_result", lambda x: (x == "SUPPORTS").sum()),
            contradicting_evidence=("evidence_result", lambda x: (x == "CONTRADICTS").sum()),
        )
        .reset_index()
    )
    df = df.merge(evidence_summary, on="claim_id", how="left")

    emp = t["employment_records"].copy()
    emp["start_date"] = pd.to_datetime(emp["start_date"], errors="coerce")
    emp_summary = (
        emp.groupby(["trainee_id", "claim_id"])
        .agg(employment_record_count=("employment_id", "count"))
        .reset_index()
    )
    latest_emp = (
        emp.sort_values("start_date")
        .drop_duplicates(subset=["trainee_id", "claim_id"], keep="last")
        [
            [
                "trainee_id",
                "claim_id",
                "employment_id",
                "employer_id",
                "employer_name",
                "occupation",
                "employment_type",
                "start_date",
                "end_date",
                "data_source",
                "verification_status",
            ]
        ]
        .copy()
    )
    emp_summary = emp_summary.merge(latest_emp, on=["trainee_id", "claim_id"], how="left")
    df = df.merge(emp_summary, on=["trainee_id", "claim_id"], how="left", suffixes=("", "_employment"))

    if "employer_id" in df.columns:
        df = df.merge(t["employers"], on="employer_id", how="left", suffixes=("", "_employer"))

    fu = (
        t["followups"]
        .groupby(["trainee_id", "claim_id"])
        .agg(followup_count=("followup_id", "count"))
        .reset_index()
    )
    df = df.merge(fu, on=["trainee_id", "claim_id"], how="left")

    wage_summary = (
        t["wage_records"]
        .groupby("trainee_id")
        .agg(wage_records_count=("wage_id", "count"))
        .reset_index()
    )
    df = df.merge(wage_summary, on="trainee_id", how="left")

    tr = (
        t["transitions"]
        .groupby("trainee_id")
        .agg(transition_count=("transition_id", "count"))
        .reset_index()
    )
    df = df.merge(tr, on="trainee_id", how="left")

    for col in [
        "evidence_count",
        "supporting_evidence",
        "contradicting_evidence",
        "followup_count",
        "wage_records_count",
        "transition_count",
        "employment_record_count",
    ]:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    # Prefer verification status from verification table
    if "verification_status_verification" not in df.columns:
        if "verification_status" in df.columns:
            df["verification_status_verification"] = df["verification_status"]
        else:
            df["verification_status_verification"] = "PENDING"

    return df


def _ver_col(df: pd.DataFrame) -> str:
    if "verification_status_verification" in df.columns:
        return "verification_status_verification"
    return "verification_status"


def programme_summary() -> Dict[str, Any]:
    df = build_analytical_dataset()
    t = load_tables()
    ver = _ver_col(df)

    outcomes = df["outcome_type"].value_counts(dropna=False).to_dict()
    outcomes = {str(k): int(v) for k, v in outcomes.items()}

    att = df["attendance_percentage"].dropna() if "attendance_percentage" in df.columns else pd.Series(dtype=float)
    assess = df["assessment_score"].dropna() if "assessment_score" in df.columns else pd.Series(dtype=float)

    return {
        "total_trainees": int(df["trainee_id"].nunique()),
        "total_claims": int(df["claim_id"].nunique()) if "claim_id" in df.columns else 0,
        "outcomes": outcomes,
        "employment_rate": float(round(df["outcome_type"].eq("EMPLOYED").mean() * 100, 1)),
        "positive_outcome_rate": float(
            round(
                df["outcome_type"]
                .isin(["EMPLOYED", "APPRENTICESHIP", "SELF_EMPLOYED", "HIGHER_EDUCATION"])
                .mean()
                * 100,
                1,
            )
        ),
        "independent_evidence_rate": float(
            round(df[ver].isin(["SUPPORTED", "CORROBORATED"]).mean() * 100, 1)
        ),
        "followup_response_rate": float(
            round(t["followups"]["response_status"].eq("RESPONDED").mean() * 100, 1)
        ),
        "wage_verification_rate": float(
            round(t["wage_records"]["verification_status"].eq("VERIFIED").mean() * 100, 1)
        )
        if "verification_status" in t["wage_records"].columns
        else 0.0,
        "average_attendance": float(round(att.mean(), 1)) if len(att) else 0.0,
        "average_assessment": float(round(assess.mean(), 1)) if len(assess) else 0.0,
        "verification_status": {
            str(k): int(v) for k, v in df[ver].value_counts(dropna=False).to_dict().items()
        },
    }


def calculate_retention(checkpoint: str) -> Dict[str, Any]:
    df = build_analytical_dataset()
    t = load_tables()
    followups = t["followups"]

    baseline = df[df["outcome_type"] == "EMPLOYED"][["trainee_id", "claim_id", "outcome_type"]].drop_duplicates(
        "trainee_id"
    )
    eligible = len(baseline)

    fu = followups[followups["checkpoint"] == checkpoint].copy()
    merged = baseline.merge(
        fu[["trainee_id", "response_status", "outcome"]],
        on="trainee_id",
        how="left",
    )

    observed = merged["response_status"].eq("RESPONDED")
    retained = observed & merged["outcome"].eq("EMPLOYED")
    no_response = merged["response_status"].eq("NO_RESPONSE")
    not_observed = merged["response_status"].isna()

    obs_n = int(observed.sum())
    ret_n = int(retained.sum())

    retention_rate = round(ret_n / obs_n * 100, 1) if obs_n > 0 else None
    coverage_rate = round(obs_n / eligible * 100, 1) if eligible > 0 else None

    return {
        "checkpoint": checkpoint,
        "baseline_employed": eligible,
        "observed": obs_n,
        "retained": ret_n,
        "no_response": int(no_response.sum()),
        "not_observed": int(not_observed.sum()),
        "retention_rate_observed": retention_rate,
        "coverage_rate": coverage_rate,
    }


def retention_summary() -> Dict[str, Any]:
    rows = [calculate_retention(cp) for cp in ("3M", "6M", "12M")]
    return {"checkpoints": rows}


def wage_progression() -> Dict[str, Any]:
    t = load_tables()
    wage_band_order = {"<10K": 1, "10K-15K": 2, "15K-20K": 3, "20K-30K": 4, ">30K": 5}

    wage = t["wage_records"].copy()
    wage["effective_from"] = pd.to_datetime(wage["effective_from"], errors="coerce")
    wage["wage_rank"] = wage["wage_band"].map(wage_band_order)
    wage = wage.sort_values(["trainee_id", "effective_from"])

    records: List[Dict[str, Any]] = []
    for trainee_id, group in wage.groupby("trainee_id"):
        group = group.sort_values("effective_from")
        if len(group) < 2:
            continue
        first, last = group.iloc[0], group.iloc[-1]
        fr, lr = first["wage_rank"], last["wage_rank"]
        if pd.isna(fr) or pd.isna(lr):
            change = "UNKNOWN"
        elif lr > fr:
            change = "WAGE_INCREASE"
        elif lr < fr:
            change = "WAGE_DECREASE"
        else:
            change = "NO_CHANGE"
        records.append(
            {
                "trainee_id": str(trainee_id),
                "first_wage_band": first["wage_band"],
                "latest_wage_band": last["wage_band"],
                "first_date": str(first["effective_from"]) if pd.notna(first["effective_from"]) else None,
                "latest_date": str(last["effective_from"]) if pd.notna(last["effective_from"]) else None,
                "wage_change": change,
            }
        )

    table = pd.DataFrame(records)
    if table.empty:
        return {
            "measurable_cases": 0,
            "wage_increases": 0,
            "wage_decreases": 0,
            "no_change": 0,
            "progression_rate": None,
            "records": [],
            "distribution": {},
        }

    increases = int(table["wage_change"].eq("WAGE_INCREASE").sum())
    decreases = int(table["wage_change"].eq("WAGE_DECREASE").sum())
    no_change = int(table["wage_change"].eq("NO_CHANGE").sum())
    n = len(table)

    return {
        "measurable_cases": n,
        "wage_increases": increases,
        "wage_decreases": decreases,
        "no_change": no_change,
        "progression_rate": round(increases / n * 100, 1) if n else None,
        "distribution": {str(k): int(v) for k, v in table["wage_change"].value_counts().to_dict().items()},
        "records": records[:50],
    }


def provider_performance() -> List[Dict[str, Any]]:
    df = build_analytical_dataset()
    ver = _ver_col(df)

    provider_analysis = (
        df.groupby("provider_name")
        .agg(
            trainees=("trainee_id", "nunique"),
            employed=("outcome_type", lambda x: (x == "EMPLOYED").sum()),
            unemployed=("outcome_type", lambda x: (x == "UNEMPLOYED").sum()),
            reported=(ver, lambda x: (x == "REPORTED").sum()),
            conflict=(ver, lambda x: (x == "CONFLICT").sum()),
            unknown=(ver, lambda x: (x == "UNKNOWN").sum()),
        )
        .reset_index()
    )
    provider_analysis["employment_rate"] = (
        provider_analysis["employed"] / provider_analysis["trainees"] * 100
    ).round(1)
    provider_analysis["problem_rate"] = (
        (provider_analysis["conflict"] + provider_analysis["unknown"])
        / provider_analysis["trainees"]
        * 100
    ).round(1)
    provider_analysis["reported_rate"] = (
        provider_analysis["reported"] / provider_analysis["trainees"] * 100
    ).round(1)

    mean_emp = provider_analysis["employment_rate"].mean()
    provider_analysis["employment_deviation"] = (
        provider_analysis["employment_rate"] - mean_emp
    ).round(1)
    provider_analysis["evidence_review"] = provider_analysis["problem_rate"] > 5
    provider_analysis["reporting_review"] = provider_analysis["reported_rate"] > 20
    provider_analysis["outcome_review"] = provider_analysis["employment_rate"] < 30
    provider_analysis["review_count"] = provider_analysis[
        ["evidence_review", "reporting_review", "outcome_review"]
    ].sum(axis=1)
    provider_analysis["attention_level"] = pd.cut(
        provider_analysis["review_count"],
        bins=[-1, 0, 1, 2, 3],
        labels=["NORMAL", "MONITOR", "REVIEW", "PRIORITY_REVIEW"],
    )

    rows = []
    for _, r in provider_analysis.iterrows():
        rows.append(
            {
                "provider_name": r["provider_name"],
                "trainees": int(r["trainees"]),
                "employed": int(r["employed"]),
                "employment_rate": float(r["employment_rate"]),
                "problem_rate": float(r["problem_rate"]),
                "reported_rate": float(r["reported_rate"]),
                "employment_deviation": float(r["employment_deviation"]),
                "review_count": int(r["review_count"]),
                "attention_level": str(r["attention_level"]),
            }
        )
    rows.sort(key=lambda x: x["review_count"], reverse=True)
    return rows


def progression_signals() -> Dict[str, Any]:
    """Live values for the Analytics 'Progression signals' cards."""
    summary = programme_summary()
    retention = retention_summary()
    wages = wage_progression()
    providers = provider_performance()

    # Employment progression: share still employed among observed 3M follow-ups
    r3 = next((c for c in retention["checkpoints"] if c["checkpoint"] == "3M"), {})
    emp_prog = r3.get("retention_rate_observed")
    emp_label = f"{emp_prog}%" if emp_prog is not None else "N/A"
    emp_detail = (
        f"{r3.get('retained', 0)} of {r3.get('observed', 0)} observed employed "
        f"trainees still employed at 3 months"
        if r3.get("observed")
        else "Insufficient 3M follow-up observations"
    )

    wage_rate = wages.get("progression_rate")
    wage_label = f"{wage_rate}%" if wage_rate is not None else "N/A"
    wage_detail = (
        f"{wages.get('wage_increases', 0)} increases among "
        f"{wages.get('measurable_cases', 0)} measurable wage cases"
        if wages.get("measurable_cases")
        else "Need ≥2 wage records per trainee"
    )

    # Evidence freshness: claims that are REPORTED/CONFLICT/UNKNOWN need refresh
    ver = summary.get("verification_status", {})
    needs = int(ver.get("REPORTED", 0) + ver.get("CONFLICT", 0) + ver.get("UNKNOWN", 0) + ver.get("PENDING", 0))
    total = summary.get("total_claims") or 1
    freshness_pct = round(needs / total * 100, 1)
    fresh_label = f"{freshness_pct}%"
    fresh_detail = f"{needs} claims need stronger or updated verification"

    review_providers = sum(1 for p in providers if p["attention_level"] != "NORMAL")

    return {
        "employment_progression": {
            "value": emp_label,
            "metric": emp_prog,
            "description": emp_detail,
        },
        "wage_progression": {
            "value": wage_label,
            "metric": wage_rate,
            "description": wage_detail,
        },
        "evidence_freshness": {
            "value": fresh_label,
            "metric": freshness_pct,
            "description": fresh_detail,
            "claims_needing_review": needs,
        },
        "providers_requiring_review": review_providers,
        "programme": summary,
        "retention": retention,
    }


def outcomes_by_course() -> List[Dict[str, Any]]:
    df = build_analytical_dataset()
    rows = []
    for course, g in df.groupby("course_name"):
        n = g["trainee_id"].nunique()
        employed = int((g["outcome_type"] == "EMPLOYED").sum())
        rows.append(
            {
                "course_name": course,
                "trainees": int(n),
                "employed": employed,
                "employment_rate": round(employed / n * 100, 1) if n else 0,
            }
        )
    rows.sort(key=lambda x: x["employment_rate"], reverse=True)
    return rows


def clear_cache() -> None:
    load_tables.cache_clear()
