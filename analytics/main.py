"""
Offline exploratory analytics (pandas).

Run from the project root:

    cd "Kaushal trace backend"
    python analytics/offline_main.py

For the live dashboard, the same logic is exposed via FastAPI:
    GET /analytics/programme-summary
    GET /analytics/retention-summary
    GET /analytics/wage-progression
    GET /analytics/provider-attention
    GET /analytics/progression-signals
    GET /analytics/course-outcome-rates
"""

import pandas as pd
import numpy as np

# ============================================================
# 1. LOAD DATA
# ============================================================

trainees = pd.read_csv("data/csv/trainees.csv")
training_records = pd.read_csv("data/csv/training_records.csv")
outcome_claims = pd.read_csv("data/csv/outcome_claims.csv")
evidence_records = pd.read_csv("data/csv/evidence_records.csv")
verification_records = pd.read_csv("data/csv/verification_records.csv")
employment_records = pd.read_csv("data/csv/employment_records.csv")
wage_records = pd.read_csv("data/csv/wage_records.csv")
followups = pd.read_csv("data/csv/followups.csv")
transitions = pd.read_csv("data/csv/transitions.csv")
employers = pd.read_csv("data/csv/employers.csv")
providers = pd.read_csv("data/csv/providers.csv")
courses = pd.read_csv("data/csv/courses.csv")


# ============================================================
# 2. START WITH TRAINEE + TRAINING
# ============================================================

analytical_dataset = (
    trainees
    .merge(
        training_records,
        on="trainee_id",
        how="left",
        suffixes=("", "_training")
    )
)


# ============================================================
# 3. ADD COURSE INFORMATION
# ============================================================

analytical_dataset = analytical_dataset.merge(
    courses,
    on="course_id",
    how="left",
    suffixes=("", "_course")
)


# ============================================================
# 4. ADD PROVIDER INFORMATION
# ============================================================

analytical_dataset = analytical_dataset.merge(
    providers,
    on="provider_id",
    how="left",
    suffixes=("", "_provider")
)


# ============================================================
# 5. ADD OUTCOME CLAIM
# ============================================================

analytical_dataset = analytical_dataset.merge(
    outcome_claims,
    on=["trainee_id", "training_id"],
    how="left",
    suffixes=("", "_claim")
)

assert not analytical_dataset.duplicated(
    subset=["trainee_id", "training_id", "claim_id"]
).any(), (
    "ERROR: analytical_dataset contains duplicate trainee/training/claim rows."
)

# ============================================================
# 6. ADD VERIFICATION RESULT
# ============================================================

# One claim may have multiple verification records.
# For now, keep the latest/most relevant record per claim
# if verification_id exists.

verification_latest = verification_records.copy()

verification_latest["verified_at"] = pd.to_datetime(
    verification_latest["verified_at"],
    errors="coerce"
)

verification_latest = (
    verification_latest
    .sort_values("verified_at")
    .drop_duplicates(
        subset=["claim_id"],
        keep="last"
    )
)


analytical_dataset = analytical_dataset.merge(
    verification_latest,
    on="claim_id",
    how="left",
    suffixes=("", "_verification")
)


# ============================================================
# 7. EVIDENCE SUMMARY
# ============================================================

evidence_summary = (
    evidence_records
    .groupby("claim_id")
    .agg(
        evidence_count=("evidence_id", "count"),

        supporting_evidence=(
            "evidence_result",
            lambda x: (x == "SUPPORTS").sum()
        ),

        contradicting_evidence=(
            "evidence_result",
            lambda x: (x == "CONTRADICTS").sum()
        )
    )
    .reset_index()
)


analytical_dataset = analytical_dataset.merge(
    evidence_summary,
    on="claim_id",
    how="left"
)


# ============================================================
# 8. ADD EMPLOYMENT INFORMATION
# ============================================================

employment_analysis = employment_records.copy()

employment_analysis["start_date"] = pd.to_datetime(
    employment_analysis["start_date"],
    errors="coerce"
)

employment_analysis["end_date"] = pd.to_datetime(
    employment_analysis["end_date"],
    errors="coerce"
)

# Number of employment records per trainee/claim
employment_summary = (
    employment_analysis
    .groupby(["trainee_id", "claim_id"])
    .agg(
        employment_record_count=("employment_id", "count")
    )
    .reset_index()
)

# Latest employment record for descriptive information
latest_employment = (
    employment_analysis
    .sort_values("start_date")
    .drop_duplicates(
        subset=["trainee_id", "claim_id"],
        keep="last"
    )
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
            "verification_status"
        ]
    ]
    .copy()
)

# Combine count + latest employment information
employment_summary = employment_summary.merge(
    latest_employment,
    on=["trainee_id", "claim_id"],
    how="left"
)

analytical_dataset = analytical_dataset.merge(
    employment_summary,
    on=["trainee_id", "claim_id"],
    how="left",
    suffixes=("", "_employment")
)


# ============================================================
# 9. ADD EMPLOYER INFORMATION
# ============================================================

if "employer_id" in analytical_dataset.columns:

    analytical_dataset = analytical_dataset.merge(
        employers,
        on="employer_id",
        how="left",
        suffixes=("", "_employer")
    )


# ============================================================
# 10. ADD FOLLOW-UP INFORMATION
# ============================================================

followup_summary = (
    followups
    .groupby(["trainee_id", "claim_id"])
    .agg(
        followup_count=("followup_id", "count")
    )
    .reset_index()
)


analytical_dataset = analytical_dataset.merge(
    followup_summary,
    on=["trainee_id", "claim_id"],
    how="left"
)


# ============================================================
# 11. ADD WAGE INFORMATION
# ============================================================

wage_analysis = wage_records.copy()

wage_analysis["effective_from"] = pd.to_datetime(
    wage_analysis["effective_from"],
    errors="coerce"
)

wage_summary = (
    wage_analysis
    .groupby(["trainee_id"])
    .agg(
        wage_records_count=("wage_id", "count")
    )
    .reset_index()
)

analytical_dataset = analytical_dataset.merge(
    wage_summary,
    on="trainee_id",
    how="left"
)

# ============================================================
# 12. ADD TRANSITION COUNT
# ============================================================

transition_summary = (
    transitions
    .groupby("trainee_id")
    .agg(
        transition_count=("transition_id", "count")
    )
    .reset_index()
)


analytical_dataset = analytical_dataset.merge(
    transition_summary,
    on="trainee_id",
    how="left"
)


# ============================================================
# 13. CLEAN COUNTS
# ============================================================

count_columns = [
    "evidence_count",
    "supporting_evidence",
    "contradicting_evidence",
    "followup_count",
    "wage_records_count",
    "transition_count"
]

for col in count_columns:
    if col in analytical_dataset.columns:
        analytical_dataset[col] = (
            analytical_dataset[col]
            .fillna(0)
            .astype(int)
        )


# ============================================================
# 14. BASIC OUTPUT
# ============================================================

print("\n==============================")
print("ANALYTICAL DATASET")
print("==============================")

print("Shape:")
print(analytical_dataset.shape)

print("\nColumns:")
print(analytical_dataset.columns.tolist())

print("\nFirst 5 rows:")
print(analytical_dataset.head())

print("\nData types:")
print(analytical_dataset.dtypes)

print("\nMissing values:")
print(
    analytical_dataset.isna().sum()
    .sort_values(ascending=False)
)

print("\nDuplicate rows:")
print(analytical_dataset.duplicated().sum())

print("========== ROW GRAIN ==========")

print("Rows:", len(analytical_dataset))

print("Unique trainees:",
      analytical_dataset["trainee_id"].nunique())

print("Unique training records:",
      analytical_dataset["training_id"].nunique())

print("Unique outcome claims:",
      analytical_dataset["claim_id"].nunique())


print("\n========== OUTCOME TYPES ==========")

print(
    analytical_dataset["outcome_type"]
    .value_counts(dropna=False)
)


print("\n========== VERIFICATION STATUS ==========")

print(
    analytical_dataset["verification_status_verification"]
    .value_counts(dropna=False)
)


print("\n========== EMPLOYMENT ==========")

print(
    analytical_dataset["employment_id"]
    .notna()
    .value_counts()
)

print("\nEmployment records per trainee:")
print(
    analytical_dataset[
        ["trainee_id", "employment_record_count"]
    ]
    .dropna()
    .sort_values(
        "employment_record_count",
        ascending=False
    )
    .head(20)
)


print("\n========== TRAINEE FREQUENCY ==========")

print(
    analytical_dataset["trainee_id"]
    .value_counts()
    .sort_values(ascending=False)
    .head(20)
)


print("\n========== CLAIM FREQUENCY ==========")

print(
    analytical_dataset["claim_id"]
    .value_counts()
    .sort_values(ascending=False)
    .head(20)
)

# ==========================================
# OUTCOME ANALYTICS
# ==========================================

print("========== OVERALL OUTCOMES ==========")

outcome_counts = analytical_dataset["outcome_type"].value_counts()

print(outcome_counts)

print("\n========== OUTCOME PERCENTAGES ==========")

outcome_percentages = (
    analytical_dataset["outcome_type"]
    .value_counts(normalize=True)
    .mul(100)
    .round(2)
)

print(outcome_percentages)

print("\n========== OUTCOMES BY COURSE ==========")

course_outcomes = pd.crosstab(
    analytical_dataset["course_name"],
    analytical_dataset["outcome_type"]
)

print(course_outcomes)

print("\n========== OUTCOMES BY PROVIDER ==========")

provider_outcomes = pd.crosstab(
    analytical_dataset["provider_name"],
    analytical_dataset["outcome_type"]
)

print(provider_outcomes)

course_outcome_rates = (
    pd.crosstab(
        analytical_dataset["course_name"],
        analytical_dataset["outcome_type"],
        normalize="index"
    ) * 100
).round(1)

print(course_outcome_rates)

verification_by_outcome = pd.crosstab(
    analytical_dataset["outcome_type"],
    analytical_dataset["verification_status_verification"]
)

print(verification_by_outcome)

verification_summary = (
    analytical_dataset["verification_status_verification"]
    .value_counts()
)

verification_summary_percent = (
    verification_summary
    .div(len(analytical_dataset))
    .mul(100)
    .round(1)
)

print("========== VERIFICATION QUALITY ==========")

for status in verification_summary_percent.index:
    print(
        f"{status}: "
        f"{verification_summary[status]} "
        f"({verification_summary_percent[status]}%)"
    )

independently_supported = (
    verification_summary.get("SUPPORTED", 0)
    + verification_summary.get("CORROBORATED", 0)
)

needs_resolution = (
    verification_summary.get("CONFLICT", 0)
    + verification_summary.get("UNKNOWN", 0)
)

print("\nIndependently supported/corroborated:",
      independently_supported)

print("Needs resolution:",
      needs_resolution)

print("========== FOLLOW-UP ==========")

print(
    analytical_dataset[
        ["trainee_id", "followup_count"]
    ][analytical_dataset["followup_count"] > 0]
    .head(20)
)

print("\n========== WAGE RECORDS ==========")

print(
    analytical_dataset[
        ["trainee_id", "employment_id", "wage_records_count"]
    ][analytical_dataset["wage_records_count"] > 0]
    .head(20)
)

print("\n========== TRANSITIONS ==========")

print(
    analytical_dataset[
        ["trainee_id", "transition_count"]
    ][analytical_dataset["transition_count"] > 0]
    .head(20)
)

print("\n========== COUNTS ==========")

print("Trainees with follow-ups:",
      (analytical_dataset["followup_count"] > 0).sum())

print("Trainees with wage records:",
      (analytical_dataset["wage_records_count"] > 0).sum())

print("Trainees with transitions:",
      (analytical_dataset["transition_count"] > 0).sum())

print("========== FOLLOW-UP DETAILS ==========")

print(
    followups[
        [
            "followup_id",
            "trainee_id",
            "claim_id",
            "checkpoint",
            "response_status",
            "outcome"
        ]
    ].head(30)
)

print("========== WAGE RECORD DETAILS ==========")

print(
    wage_records.head(20)
)

print("\n========== WAGE COLUMNS ==========")

print(wage_records.columns.tolist())

print("========== WAGE BAND DISTRIBUTION ==========")

print(
    wage_records["wage_band"]
    .value_counts(dropna=False)
)

print("\n========== WAGE VERIFICATION ==========")

print(
    pd.crosstab(
        wage_records["wage_band"],
        wage_records["verification_status"]
    )
)

print("\n========== WAGE SOURCE ==========")

print(
    pd.crosstab(
        wage_records["data_source"],
        wage_records["verification_status"]
    )
)

provider_analysis = (
    analytical_dataset
    .groupby("provider_name")
    .agg(
        trainees=("trainee_id", "nunique"),
        employed=("outcome_type", lambda x: (x == "EMPLOYED").sum()),
        unemployed=("outcome_type", lambda x: (x == "UNEMPLOYED").sum()),
        reported=("verification_status_verification", lambda x: (x == "REPORTED").sum()),
        conflict=("verification_status_verification", lambda x: (x == "CONFLICT").sum()),
        unknown=("verification_status_verification", lambda x: (x == "UNKNOWN").sum())
    )
    .reset_index()
)

provider_analysis["employment_rate"] = (
    provider_analysis["employed"]
    / provider_analysis["trainees"]
    * 100
).round(1)

provider_analysis["problem_rate"] = (
    (provider_analysis["conflict"] + provider_analysis["unknown"])
    / provider_analysis["trainees"]
    * 100
).round(1)

print(provider_analysis)

print(
    provider_analysis[
        [
            "provider_name",
            "trainees",
            "employed",
            "employment_rate",
            "reported",
            "conflict",
            "unknown",
            "problem_rate"
        ]
    ].sort_values(
        "problem_rate",
        ascending=False
    )
)

print("========== PROVIDER BASELINES ==========")

print("Mean employment rate:",
      round(provider_analysis["employment_rate"].mean(), 2))

print("Mean problem rate:",
      round(provider_analysis["problem_rate"].mean(), 2))

print("Mean reported claims:",
      round(provider_analysis["reported"].mean(), 2))

print("Mean trainees per provider:",
      round(provider_analysis["trainees"].mean(), 2))

provider_analysis["employment_deviation"] = (
    provider_analysis["employment_rate"]
    - provider_analysis["employment_rate"].mean()
).round(1)

provider_analysis["reported_rate"] = (
    provider_analysis["reported"]
    / provider_analysis["trainees"]
    * 100
).round(1)

print(
    provider_analysis[
        [
            "provider_name",
            "employment_rate",
            "employment_deviation",
            "problem_rate",
            "reported_rate"
        ]
    ]
)

provider_analysis["evidence_review"] = (
    provider_analysis["problem_rate"] > 5
)

provider_analysis["reporting_review"] = (
    provider_analysis["reported_rate"] > 20
)

provider_analysis["outcome_review"] = (
    provider_analysis["employment_rate"] < 30
)

provider_analysis["review_count"] = (
    provider_analysis[
        [
            "evidence_review",
            "reporting_review",
            "outcome_review"
        ]
    ]
    .sum(axis=1)
)

print(
    provider_analysis[
        [
            "provider_name",
            "employment_rate",
            "problem_rate",
            "reported_rate",
            "evidence_review",
            "reporting_review",
            "outcome_review",
            "review_count"
        ]
    ]
    .sort_values("review_count", ascending=False)
)

provider_analysis["attention_level"] = pd.cut(
    provider_analysis["review_count"],
    bins=[-1, 0, 1, 2, 3],
    labels=[
        "NORMAL",
        "MONITOR",
        "REVIEW",
        "PRIORITY_REVIEW"
    ]
)

print(
    provider_analysis[
        [
            "provider_name",
            "employment_rate",
            "problem_rate",
            "reported_rate",
            "review_count",
            "attention_level"
        ]
    ]
    .sort_values(
        "review_count",
        ascending=False
    )
)

programme_summary = {
    "total_trainees": int(analytical_dataset["trainee_id"].nunique()),

    "outcomes": (
        analytical_dataset["outcome_type"]
        .value_counts()
        .to_dict()
    ),

    "employment_rate": float(round(
        analytical_dataset["outcome_type"]
        .eq("EMPLOYED")
        .mean() * 100,
        1
    )),

    "independent_evidence_rate": float(round(
        analytical_dataset["verification_status_verification"]
        .isin(["SUPPORTED", "CORROBORATED"])
        .mean() * 100,
        1
    )),

    "followup_response_rate": float(round(
        followups["response_status"]
        .eq("RESPONDED")
        .mean() * 100,
        1
    )),

    "wage_verification_rate": float(round(
        wage_records["verification_status"]
        .eq("VERIFIED")
        .mean() * 100,
        1
    )),

    "providers_requiring_review": int(
        (
            provider_analysis["attention_level"] != "NORMAL"
        ).sum()
    )
}

print(programme_summary)

print("========== LONGITUDINAL COVERAGE ==========")

print("Total trainees:", analytical_dataset["trainee_id"].nunique())

print("Follow-up records:", len(followups))

print(
    "Unique follow-up trainees:",
    followups["trainee_id"].nunique()
)

print(
    "Checkpoints:",
    followups["checkpoint"].value_counts().to_dict()
)

print(
    "Career transitions:",
    len(transitions)
)

print(
    "Trainees with transitions:",
    transitions["trainee_id"].nunique()
)

print(
    "Wage records:",
    len(wage_records)
)

print(
    "Trainees with wage records:",
    wage_records["trainee_id"].nunique()
)

assisted_candidates = analytical_dataset[
    analytical_dataset["verification_status_verification"]
    .isin(["REPORTED", "CONFLICT", "UNKNOWN"])
]

print("Potential assisted cases:", len(assisted_candidates))

print(
    assisted_candidates[
        [
            "trainee_id",
            "outcome_type",
            "verification_status_verification"
        ]
    ].to_string(index=False)
)

candidate_ids = set(
    assisted_candidates["trainee_id"]
)

followup_ids = set(
    followups["trainee_id"]
)

print("Candidate cases:", len(candidate_ids))
print("Follow-up trainees:", len(followup_ids))

print(
    "Missing follow-ups:",
    sorted(candidate_ids - followup_ids)
)

print(
    "Unexpected follow-ups:",
    sorted(followup_ids - candidate_ids)
)

print(
    followups[
        [
            "followup_id",
            "trainee_id",
            "claim_id",
            "checkpoint",
            "response_status",
            "outcome"
        ]
    ].sort_values("trainee_id").to_string(index=False)
)

followup_check = (
    followups[
        ["trainee_id", "claim_id", "response_status", "outcome"]
    ]
    .merge(
        analytical_dataset[
            [
                "trainee_id",
                "claim_id",
                "outcome_type",
                "verification_status_verification"
            ]
        ],
        on=["trainee_id", "claim_id"],
        how="left",
        indicator=True
    )
)

print(followup_check.to_string(index=False))

# Create a 3-month longitudinal view for ALL trainees

followup_3m = (
    followups[followups["checkpoint"] == "3M"]
    [
        [
            "trainee_id",
            "response_status",
            "outcome"
        ]
    ]
    .copy()
)

three_month = analytical_dataset[
    [
        "trainee_id",
        "outcome_type"
    ]
].copy()

three_month = three_month.merge(
    followup_3m,
    on="trainee_id",
    how="left"
)

three_month["three_month_status"] = np.select(
    [
        three_month["response_status"].eq("RESPONDED"),
        three_month["response_status"].eq("NO_RESPONSE"),
        three_month["response_status"].isna()
    ],
    [
        "OBSERVED",
        "ATTEMPTED_NO_RESPONSE",
        "NOT_OBSERVED"
    ],
    default="UNKNOWN"
)

three_month["three_month_outcome"] = three_month["outcome"].where(
    three_month["three_month_status"].eq("OBSERVED")
)

print(
    three_month[
        [
            "trainee_id",
            "outcome_type",
            "three_month_status",
            "three_month_outcome"
        ]
    ].head(20)
)

print("\n========== 3M STATUS ==========")
print(
    three_month["three_month_status"]
    .value_counts()
)

observed_3m = three_month[
    three_month["three_month_status"] == "OBSERVED"
].copy()

print("========== OBSERVED 3M OUTCOMES ==========")

print(
    observed_3m[
        [
            "trainee_id",
            "outcome_type",
            "three_month_outcome"
        ]
    ].to_string(index=False)
)

print("\n========== 3M TRANSITIONS ==========")

transition_table = pd.crosstab(
    observed_3m["outcome_type"],
    observed_3m["three_month_outcome"]
)

print(transition_table)

observed_3m["same_outcome"] = (
    observed_3m["outcome_type"]
    == observed_3m["three_month_outcome"]
)

print("========== 3M OUTCOME CONTINUITY ==========")

print(
    observed_3m[
        [
            "trainee_id",
            "outcome_type",
            "three_month_outcome",
            "same_outcome"
        ]
    ].to_string(index=False)
)

same_outcome_count = observed_3m["same_outcome"].sum()
observed_count = len(observed_3m)

print("\nObserved trainees:", observed_count)
print("Same outcome:", same_outcome_count)
print(
    "Outcome continuity among observed respondents:",
    round(same_outcome_count / observed_count * 100, 1),
    "%"
)

# Detect actual outcome transitions

observed_3m["transition_type"] = np.select(
    [
        observed_3m["three_month_outcome"].eq(
            observed_3m["outcome_type"]
        ),
        observed_3m["three_month_outcome"].notna()
    ],
    [
        "NO_CHANGE",
        "OUTCOME_CHANGED"
    ],
    default="UNKNOWN"
)

print("========== 3M TRANSITION ANALYSIS ==========")

print(
    observed_3m[
        [
            "trainee_id",
            "outcome_type",
            "three_month_outcome",
            "transition_type"
        ]
    ].to_string(index=False)
)

print("\n========== TRANSITION COUNTS ==========")

print(
    observed_3m["transition_type"]
    .value_counts()
)

# Prepare wage records for longitudinal analysis

wage_analysis = wage_records.copy()

wage_analysis["effective_from"] = pd.to_datetime(
    wage_analysis["effective_from"],
    errors="coerce"
)

wage_analysis = wage_analysis.sort_values(
    ["trainee_id", "effective_from"]
)

print(wage_analysis[
    [
        "trainee_id",
        "employment_id",
        "wage_band",
        "effective_from",
        "verification_status"
    ]
].head(15))

wage_counts = (
    wage_analysis
    .groupby("trainee_id")
    .size()
    .reset_index(name="wage_observations")
)

print("========== WAGE OBSERVATIONS PER TRAINEE ==========")

print(
    wage_counts["wage_observations"]
    .value_counts()
    .sort_index()
)

measurable = (
    wage_counts["wage_observations"] >= 2
).sum()

total_with_wage = len(wage_counts)

print("\n========== WAGE PROGRESSION COVERAGE ==========")

print("Trainees with wage records:", total_with_wage)
print("Trainees with measurable progression:", measurable)

print(
    "Progression coverage:",
    round(measurable / total_with_wage * 100, 1),
    "%"
)

# ============================================================
# 15. EXTENDED SIH26135 ANALYTICS
# ============================================================
#
# This section adds:
#
# 1. District analytics
# 2. Demographic analytics
# 3. 3M / 6M / 12M retention
# 4. Non-placement reason analysis
# 5. Employment attrition reason analysis
# 6. Training -> occupation relevance
# 7. Wage progression analysis
# 8. Potential skill-gap analysis
#
# IMPORTANT:
# - UNKNOWN is not treated as UNEMPLOYED.
# - NO_RESPONSE is not treated as failure.
# - User-reported information is not treated as independently verified.
# - Skill-gap outputs are signals for investigation, not diagnoses.
# ============================================================


# ============================================================
# 15.1 DISTRICT OUTCOME ANALYTICS
# ============================================================

print("\n")
print("============================================================")
print("1. DISTRICT OUTCOME ANALYTICS")
print("============================================================")

district_outcomes = (
    analytical_dataset
    .groupby("district")
    .agg(
        trainees=("trainee_id", "nunique"),

        employed=(
            "outcome_type",
            lambda x: (x == "EMPLOYED").sum()
        ),

        self_employed=(
            "outcome_type",
            lambda x: (x == "SELF_EMPLOYED").sum()
        ),

        apprenticeship=(
            "outcome_type",
            lambda x: (x == "APPRENTICESHIP").sum()
        ),

        higher_education=(
            "outcome_type",
            lambda x: (x == "HIGHER_EDUCATION").sum()
        ),

        seeking_work=(
            "outcome_type",
            lambda x: (x == "SEEKING_WORK").sum()
        ),

        unemployed=(
            "outcome_type",
            lambda x: (x == "UNEMPLOYED").sum()
        ),

        unknown=(
            "outcome_type",
            lambda x: (x == "UNKNOWN").sum()
        )
    )
    .reset_index()
)

district_outcomes["employment_rate"] = (
    district_outcomes["employed"]
    / district_outcomes["trainees"]
    * 100
).round(1)

district_outcomes["livelihood_outcome_rate"] = (
    (
        district_outcomes["employed"]
        + district_outcomes["self_employed"]
        + district_outcomes["apprenticeship"]
    )
    / district_outcomes["trainees"]
    * 100
).round(1)

district_outcomes["unknown_rate"] = (
    district_outcomes["unknown"]
    / district_outcomes["trainees"]
    * 100
).round(1)

print(district_outcomes)


print("\n========== DISTRICT EMPLOYMENT RATE ==========")

print(
    district_outcomes[
        [
            "district",
            "trainees",
            "employed",
            "employment_rate",
            "livelihood_outcome_rate",
            "unknown_rate"
        ]
    ]
    .sort_values(
        "employment_rate",
        ascending=False
    )
    .to_string(index=False)
)


# ============================================================
# 15.2 DEMOGRAPHIC ANALYTICS
# ============================================================

print("\n")
print("============================================================")
print("2. DEMOGRAPHIC ANALYTICS")
print("============================================================")


def demographic_analysis(df, column_name):

    if column_name not in df.columns:

        print(
            f"\n[SKIPPED] Demographic column "
            f"'{column_name}' not found."
        )

        return None

    result = (
        df
        .groupby(column_name)
        .agg(
            trainees=("trainee_id", "nunique"),

            employed=(
                "outcome_type",
                lambda x: (x == "EMPLOYED").sum()
            ),

            self_employed=(
                "outcome_type",
                lambda x: (x == "SELF_EMPLOYED").sum()
            ),

            apprenticeship=(
                "outcome_type",
                lambda x: (x == "APPRENTICESHIP").sum()
            ),

            higher_education=(
                "outcome_type",
                lambda x: (x == "HIGHER_EDUCATION").sum()
            ),

            seeking_work=(
                "outcome_type",
                lambda x: (x == "SEEKING_WORK").sum()
            ),

            unemployed=(
                "outcome_type",
                lambda x: (x == "UNEMPLOYED").sum()
            ),

            unknown=(
                "outcome_type",
                lambda x: (x == "UNKNOWN").sum()
            )
        )
        .reset_index()
    )

    result["employment_rate"] = (
        result["employed"]
        / result["trainees"]
        * 100
    ).round(1)

    result["unknown_rate"] = (
        result["unknown"]
        / result["trainees"]
        * 100
    ).round(1)

    return result


print("\n========== GENDER ANALYTICS ==========")

gender_analytics = demographic_analysis(
    analytical_dataset,
    "gender"
)

if gender_analytics is not None:
    print(gender_analytics.to_string(index=False))


print("\n========== AGE GROUP ANALYTICS ==========")

age_analytics = demographic_analysis(
    analytical_dataset,
    "age_group"
)

if age_analytics is not None:
    print(age_analytics.to_string(index=False))


print("\n========== EDUCATION ANALYTICS ==========")

education_analytics = demographic_analysis(
    analytical_dataset,
    "education_level"
)

if education_analytics is not None:
    print(education_analytics.to_string(index=False))


# ============================================================
# 15.3 RETENTION ANALYTICS
# ============================================================

print("\n")
print("============================================================")
print("3. RETENTION ANALYTICS")
print("============================================================")

# Retention is measured among trainees whose baseline outcome
# was EMPLOYED and whose follow-up response was actually observed.
#
# NO_RESPONSE is NOT counted as attrition.
# NOT_OBSERVED is NOT counted as attrition.
#
# Therefore we report:
#
# - Eligible baseline employed
# - Observed at checkpoint
# - Retained employed
# - Retention rate among observed
# - Observation coverage


def calculate_retention(checkpoint):

    checkpoint_followups = followups[
        followups["checkpoint"] == checkpoint
    ][
        [
            "trainee_id",
            "claim_id",
            "response_status",
            "outcome"
        ]
    ].copy()

    baseline_employed = analytical_dataset[
        analytical_dataset["outcome_type"] == "EMPLOYED"
    ][
        [
            "trainee_id",
            "claim_id"
        ]
    ].drop_duplicates()

    retention = baseline_employed.merge(
        checkpoint_followups,
        on=["trainee_id", "claim_id"],
        how="left"
    )

    retention["observed"] = (
        retention["response_status"] == "RESPONDED"
    )

    retention["retained"] = (
        retention["observed"]
        & retention["outcome"].eq("EMPLOYED")
    )

    eligible = len(retention)

    observed = int(
        retention["observed"].sum()
    )

    retained = int(
        retention["retained"].sum()
    )

    no_response = int(
        retention["response_status"]
        .eq("NO_RESPONSE")
        .sum()
    )

    not_observed = int(
        retention["response_status"]
        .isna()
        .sum()
    )

    if observed > 0:

        retention_rate = round(
            retained / observed * 100,
            1
        )

    else:

        retention_rate = np.nan

    if eligible > 0:

        coverage_rate = round(
            observed / eligible * 100,
            1
        )

    else:

        coverage_rate = np.nan

    print(f"\n========== {checkpoint} RETENTION ==========")

    print("Baseline employed:", eligible)
    print("Observed:", observed)
    print("Retained employed:", retained)
    print("No response:", no_response)
    print("Not observed:", not_observed)

    print(
        "Retention among observed:",
        retention_rate,
        "%"
    )

    print(
        "Observation coverage:",
        coverage_rate,
        "%"
    )

    return retention


retention_3m = calculate_retention("3M")
retention_6m = calculate_retention("6M")
retention_12m = calculate_retention("12M")


# ============================================================
# 15.4 RETENTION SUMMARY TABLE
# ============================================================

retention_summary = pd.DataFrame(
    [
        {
            "checkpoint": "3M",
            "baseline_employed": len(retention_3m),
            "observed": int(retention_3m["observed"].sum()),
            "retained": int(retention_3m["retained"].sum())
        },
        {
            "checkpoint": "6M",
            "baseline_employed": len(retention_6m),
            "observed": int(retention_6m["observed"].sum()),
            "retained": int(retention_6m["retained"].sum())
        },
        {
            "checkpoint": "12M",
            "baseline_employed": len(retention_12m),
            "observed": int(retention_12m["observed"].sum()),
            "retained": int(retention_12m["retained"].sum())
        }
    ]
)

retention_summary["retention_rate_observed"] = (
    retention_summary["retained"]
    / retention_summary["observed"]
    * 100
).round(1)

retention_summary["coverage_rate"] = (
    retention_summary["observed"]
    / retention_summary["baseline_employed"]
    * 100
).round(1)

print("\n========== RETENTION SUMMARY ==========")

print(
    retention_summary.to_string(index=False)
)


# ============================================================
# 15.5 NON-PLACEMENT REASON ANALYSIS
# ============================================================

print("\n")
print("============================================================")
print("4. NON-PLACEMENT REASON ANALYSIS")
print("============================================================")

# Non-placement = completed/available trainees whose current
# outcome is SEEKING_WORK or UNEMPLOYED.
#
# We search for a reason column instead of assuming one exact
# schema name.

reason_candidates = [
    "non_placement_reason",
    "nonplacement_reason",
    "placement_reason",
    "outcome_reason",
    "reason"
]

nonplacement_reason_column = None

for column in reason_candidates:

    if column in analytical_dataset.columns:

        nonplacement_reason_column = column
        break


nonplacement = analytical_dataset[
    analytical_dataset["outcome_type"]
    .isin(["SEEKING_WORK", "UNEMPLOYED"])
].copy()


if nonplacement_reason_column is not None:

    nonplacement_reason = (
        nonplacement[
            nonplacement_reason_column
        ]
        .fillna("NOT_RECORDED")
        .value_counts()
    )

    print(
        "Reason column:",
        nonplacement_reason_column
    )

    print(
        nonplacement_reason
    )

    print("\n========== NON-PLACEMENT REASONS BY OUTCOME ==========")

    print(
        pd.crosstab(
            nonplacement["outcome_type"],
            nonplacement[
                nonplacement_reason_column
            ].fillna("NOT_RECORDED")
        )
    )

else:

    print(
        "[NOT AVAILABLE] No explicit non-placement "
        "reason field exists in the current analytical dataset."
    )

    print(
        "This is a DATASET GAP, not an analytics-code failure."
    )


# ============================================================
# 15.6 EMPLOYMENT ATTRITION REASON ANALYSIS
# ============================================================

print("\n")
print("============================================================")
print("5. EMPLOYMENT ATTRITION ANALYTICS")
print("============================================================")

# We identify transitions where an employed trainee leaves
# employment or enters a non-employed state.
#
# The transition reason is treated as the recorded reason,
# not as a causal conclusion.


attrition_transitions = transitions[
    transitions["to_status"].isin(
        [
            "SEEKING_WORK",
            "UNEMPLOYED"
        ]
    )
].copy()


if len(attrition_transitions) > 0:

    print("\n========== ATTRITION EVENTS ==========")

    print(
        attrition_transitions[
            [
                "transition_id",
                "trainee_id",
                "from_status",
                "to_status",
                "transition_date",
                "reason"
            ]
        ].to_string(index=False)
    )

    print("\n========== ATTRITION REASONS ==========")

    print(
        attrition_transitions[
            "reason"
        ]
        .fillna("NOT_RECORDED")
        .value_counts()
    )

    print("\n========== ATTRITION REASONS BY DESTINATION ==========")

    print(
        pd.crosstab(
            attrition_transitions["to_status"],
            attrition_transitions[
                "reason"
            ].fillna("NOT_RECORDED")
        )
    )

else:

    print(
        "No employment attrition transitions "
        "were found in the current dataset."
    )


# ============================================================
# 15.7 TRAINING -> OCCUPATION RELEVANCE
# ============================================================

print("\n")
print("============================================================")
print("6. TRAINING -> OCCUPATION RELEVANCE")
print("============================================================")

# We do NOT define:
#
# course name != occupation
#
# as a skill gap.
#
# A trainee can intentionally change career paths.
#
# Therefore this section first looks for an explicit target
# occupation / occupation family in the course dataset.
#
# If such a field does not exist, we provide a safe fallback:
# UNKNOWN / DIFFERENT_OCCUPATION rather than pretending
# that a mismatch proves a skill gap.


course_occupation_candidates = [
    "target_occupation",
    "target_occupation_family",
    "occupation",
    "occupation_family",
    "job_role"
]

course_occupation_column = None

for column in course_occupation_candidates:

    if column in analytical_dataset.columns:

        course_occupation_column = column
        break


occupation_column = None

occupation_candidates = [
    "occupation",
    "job_role",
    "actual_occupation"
]

for column in occupation_candidates:

    if column in analytical_dataset.columns:

        # Avoid accidentally selecting the same target field
        # if only one occupation field exists.
        if column != course_occupation_column:

            occupation_column = column
            break


if (
    course_occupation_column is not None
    and occupation_column is not None
):

    relevance_data = analytical_dataset[
        [
            "trainee_id",
            "course_name",
            course_occupation_column,
            occupation_column
        ]
    ].copy()

    relevance_data[
        course_occupation_column
    ] = (
        relevance_data[
            course_occupation_column
        ]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    relevance_data[
        occupation_column
    ] = (
        relevance_data[
            occupation_column
        ]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    relevance_data["training_occupation_relevance"] = np.select(
        [
            relevance_data[
                course_occupation_column
            ].eq(
                relevance_data[
                    occupation_column
                ]
            ),

            relevance_data[
                course_occupation_column
            ].isin(["nan", "", "none"]),

            relevance_data[
                occupation_column
            ].isin(["nan", "", "none"])
        ],
        [
            "DIRECTLY_RELATED",
            "UNKNOWN",
            "UNKNOWN"
        ],
        default="DIFFERENT_OCCUPATION"
    )

    print(
        relevance_data[
            "training_occupation_relevance"
        ].value_counts()
    )

    print(
        "\n========== TRAINING/OCCUPATION RELEVANCE =========="
    )

    print(
        relevance_data.to_string(index=False)
    )

else:

    print(
        "[LIMITED] The current dataset does not contain both "
        "an explicit course target occupation and actual occupation."
    )

    print(
        "Therefore we will NOT fabricate a relevance score."
    )

    print(
        "Recommended future fields:"
    )

    print(
        "courses.csv -> target_occupation_family"
    )

    print(
        "employment_records.csv -> occupation_family"
    )


# ============================================================
# 15.8 WAGE PROGRESSION ANALYSIS
# ============================================================

print("\n")
print("============================================================")
print("7. WAGE PROGRESSION ANALYTICS")
print("============================================================")

# Define an ordered wage-band scale.
#
# This allows us to compare bands without pretending that
# the exact salary is known.


wage_band_order = {
    "<10K": 1,
    "10K-15K": 2,
    "15K-20K": 3,
    "20K-30K": 4,
    ">30K": 5
}

wage_progression = wage_analysis.copy()

wage_progression["wage_rank"] = (
    wage_progression["wage_band"]
    .map(wage_band_order)
)

wage_progression = wage_progression.sort_values(
    [
        "trainee_id",
        "effective_from"
    ]
)


def classify_wage_change(group):

    group = group.sort_values(
        "effective_from"
    ).copy()

    if len(group) < 2:

        return None

    first = group.iloc[0]
    last = group.iloc[-1]

    first_rank = first["wage_rank"]
    last_rank = last["wage_rank"]

    if pd.isna(first_rank) or pd.isna(last_rank):

        change = "UNKNOWN"

    elif last_rank > first_rank:

        change = "WAGE_INCREASE"

    elif last_rank < first_rank:

        change = "WAGE_DECREASE"

    else:

        change = "NO_CHANGE"

    return {
        "trainee_id": group["trainee_id"].iloc[0],
        "first_wage_band": first["wage_band"],
        "latest_wage_band": last["wage_band"],
        "first_date": first["effective_from"],
        "latest_date": last["effective_from"],
        "wage_change": change
    }


wage_progression_records = []

for trainee_id, group in wage_progression.groupby(
    "trainee_id"
):

    result = classify_wage_change(group)

    if result is not None:

        wage_progression_records.append(result)


wage_progression_table = pd.DataFrame(
    wage_progression_records
)


if len(wage_progression_table) > 0:

    print("\n========== WAGE PROGRESSION TABLE ==========")

    print(
        wage_progression_table.to_string(
            index=False
        )
    )

    print("\n========== WAGE CHANGE DISTRIBUTION ==========")

    print(
        wage_progression_table[
            "wage_change"
        ].value_counts()
    )

    measurable_wage_cases = len(
        wage_progression_table
    )

    wage_increases = (
        wage_progression_table[
            "wage_change"
        ]
        .eq("WAGE_INCREASE")
        .sum()
    )

    wage_decreases = (
        wage_progression_table[
            "wage_change"
        ]
        .eq("WAGE_DECREASE")
        .sum()
    )

    wage_no_change = (
        wage_progression_table[
            "wage_change"
        ]
        .eq("NO_CHANGE")
        .sum()
    )

    print(
        "\nMeasurable wage cases:",
        measurable_wage_cases
    )

    print(
        "Wage increases:",
        wage_increases
    )

    print(
        "Wage decreases:",
        wage_decreases
    )

    print(
        "No change:",
        wage_no_change
    )

    print(
        "Wage progression rate among measurable cases:",
        round(
            wage_increases
            / measurable_wage_cases
            * 100,
            1
        ),
        "%"
    )


    print("\n========== WAGE-BAND TRANSITIONS ==========")

    wage_band_transition_matrix = pd.crosstab(
        wage_progression_table[
            "first_wage_band"
        ],
        wage_progression_table[
            "latest_wage_band"
        ]
    )

    print(
        wage_band_transition_matrix
    )


else:

    print(
        "No trainees have enough wage observations "
        "for progression analysis."
    )


# ============================================================
# 15.9 WAGE PROGRESSION BY COURSE
# ============================================================

if len(wage_progression_table) > 0:

    wage_course = wage_progression_table.merge(
        analytical_dataset[
            [
                "trainee_id",
                "course_name"
            ]
        ].drop_duplicates(
            "trainee_id"
        ),
        on="trainee_id",
        how="left"
    )

    wage_course_summary = (
        wage_course
        .groupby("course_name")
        .agg(
            measurable_cases=(
                "trainee_id",
                "nunique"
            ),

            wage_increases=(
                "wage_change",
                lambda x: (
                    x == "WAGE_INCREASE"
                ).sum()
            ),

            wage_decreases=(
                "wage_change",
                lambda x: (
                    x == "WAGE_DECREASE"
                ).sum()
            ),

            no_change=(
                "wage_change",
                lambda x: (
                    x == "NO_CHANGE"
                ).sum()
            )
        )
        .reset_index()
    )

    wage_course_summary[
        "progression_rate"
    ] = (
        wage_course_summary["wage_increases"]
        / wage_course_summary["measurable_cases"]
        * 100
    ).round(1)

    print(
        "\n========== WAGE PROGRESSION BY COURSE =========="
    )

    print(
        wage_course_summary.to_string(
            index=False
        )
    )


# ============================================================
# 15.10 POTENTIAL SKILL-GAP ANALYSIS
# ============================================================

# ============================================================
# 8. POTENTIAL SKILL-GAP ANALYSIS
# ============================================================

print("\n")
print("=" * 60)
print("8. POTENTIAL SKILL-GAP ANALYSIS")
print("=" * 60)

# IMPORTANT:
# This is NOT a confirmed skill-gap detector.
# It only identifies potential mismatch signals.

skill_gap_data = analytical_dataset.copy()

# ------------------------------------------------------------
# STEP 1: Find the best available skill/course field
# ------------------------------------------------------------

course_skill_col = None

for col in [
    "skill_category",
    "course_skill_category",
    "target_occupation_family",
    "occupation_family"
]:
    if col in skill_gap_data.columns:
        course_skill_col = col
        break


# ------------------------------------------------------------
# STEP 2: Find the best available occupation field
# ------------------------------------------------------------

occupation_col = None

for col in [
    "occupation_employment",
    "occupation_claim",
    "occupation"
]:
    if col in skill_gap_data.columns:
        occupation_col = col
        break


# ------------------------------------------------------------
# STEP 3: Check whether required fields exist
# ------------------------------------------------------------

if course_skill_col is None or occupation_col is None:

    print(
        "[NOT AVAILABLE] Insufficient structured occupation/skill "
        "information for potential skill-gap analysis."
    )

    print(
        "This is a DATASET GAP, not an analytics-code failure."
    )

else:

    print("Course/skill field:", course_skill_col)
    print("Actual occupation field:", occupation_col)

    # --------------------------------------------------------
    # STEP 4: Clean text
    # --------------------------------------------------------

    skill_gap_data["course_skill_text"] = (
        skill_gap_data[course_skill_col]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    skill_gap_data["occupation_text"] = (
        skill_gap_data[occupation_col]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    # --------------------------------------------------------
    # STEP 5: Compare each row individually
    # --------------------------------------------------------

    def classify_skill_gap(row):

        course_skill = row["course_skill_text"]
        occupation = row["occupation_text"]

        if not course_skill or not occupation:
            return "UNKNOWN"

        if course_skill == occupation:
            return "NO_OBVIOUS_MISMATCH"

        if (
            course_skill in occupation
            or occupation in course_skill
        ):
            return "NO_OBVIOUS_MISMATCH"

        return "POTENTIAL_MISMATCH"


    skill_gap_data["skill_gap_signal"] = (
        skill_gap_data.apply(
            classify_skill_gap,
            axis=1
        )
    )

    # --------------------------------------------------------
    # STEP 6: Overall distribution
    # --------------------------------------------------------

    print("\n========== SKILL-GAP SIGNAL DISTRIBUTION ==========")

    print(
        skill_gap_data["skill_gap_signal"]
        .value_counts()
    )

    # --------------------------------------------------------
    # STEP 7: Potential mismatch cases
    # --------------------------------------------------------

    print("\n========== POTENTIAL SKILL-GAP CASES ==========")

    potential_cases = skill_gap_data[
        skill_gap_data["skill_gap_signal"]
        == "POTENTIAL_MISMATCH"
    ][
        [
            "trainee_id",
            "course_name",
            course_skill_col,
            occupation_col,
            "outcome_type",
            "skill_gap_signal"
        ]
    ]

    print(potential_cases)

    # --------------------------------------------------------
    # STEP 8: Course-level analysis
    # --------------------------------------------------------

    print("\n========== SKILL-GAP SIGNAL BY COURSE ==========")

    skill_gap_by_course = (
        skill_gap_data
        .groupby("course_name")
        .agg(
            trainees=("trainee_id", "nunique"),

            potential_mismatch=(
                "skill_gap_signal",
                lambda x: (
                    x == "POTENTIAL_MISMATCH"
                ).sum()
            ),

            unknown=(
                "skill_gap_signal",
                lambda x: (
                    x == "UNKNOWN"
                ).sum()
            )
        )
        .reset_index()
    )

    skill_gap_by_course["potential_mismatch_rate"] = (
        skill_gap_by_course["potential_mismatch"]
        / skill_gap_by_course["trainees"]
        * 100
    ).round(1)

    print(skill_gap_by_course)

    # --------------------------------------------------------
    # STEP 9: Interpretation
    # --------------------------------------------------------

    print("\n========== IMPORTANT INTERPRETATION ==========")

    print(
        "POTENTIAL_MISMATCH is an investigation signal, "
        "NOT a confirmed skill gap."
    )

    print(
        "A mismatch between training and occupation does not "
        "automatically mean the trainee has a skill deficiency."
    )

    print(
        "The signal should be strengthened using employer "
        "requirements, occupation families and skill taxonomies "
        "before making programme-level conclusions."
    )

# ============================================================
# 15.11 PROGRAMME IMPACT INDICATORS
# ============================================================

print("\n")
print("============================================================")
print("PROGRAMME IMPACT INDICATORS")
print("============================================================")

impact_indicators = {}

impact_indicators[
    "employment_rate"
] = round(
    (
        analytical_dataset["outcome_type"]
        .eq("EMPLOYED")
        .mean()
        * 100
    ),
    1
)

impact_indicators[
    "self_employment_rate"
] = round(
    (
        analytical_dataset["outcome_type"]
        .eq("SELF_EMPLOYED")
        .mean()
        * 100
    ),
    1
)

impact_indicators[
    "apprenticeship_rate"
] = round(
    (
        analytical_dataset["outcome_type"]
        .eq("APPRENTICESHIP")
        .mean()
        * 100
    ),
    1
)

impact_indicators[
    "higher_education_rate"
] = round(
    (
        analytical_dataset["outcome_type"]
        .eq("HIGHER_EDUCATION")
        .mean()
        * 100
    ),
    1
)

impact_indicators[
    "seeking_work_rate"
] = round(
    (
        analytical_dataset["outcome_type"]
        .eq("SEEKING_WORK")
        .mean()
        * 100
    ),
    1
)

impact_indicators[
    "unemployed_rate"
] = round(
    (
        analytical_dataset["outcome_type"]
        .eq("UNEMPLOYED")
        .mean()
        * 100
    ),
    1
)

impact_indicators[
    "unknown_rate"
] = round(
    (
        analytical_dataset["outcome_type"]
        .eq("UNKNOWN")
        .mean()
        * 100
    ),
    1
)

impact_indicators[
    "independent_evidence_rate"
] = round(
    analytical_dataset[
        "verification_status_verification"
    ]
    .isin(
        [
            "SUPPORTED",
            "CORROBORATED"
        ]
    )
    .mean()
    * 100,
    1
)

print(
    pd.Series(
        impact_indicators
    )
)


# ============================================================
# 15.12 FINAL ANALYTICS COVERAGE CHECK
# ============================================================

print("\n")
print("============================================================")
print("FINAL SIH26135 ANALYTICS COVERAGE")
print("============================================================")

analytics_checklist = {
    "District analytics": True,

    "Demographic analytics": (
        any(
            column in analytical_dataset.columns
            for column in
            [
                "gender",
                "age_group",
                "education_level"
            ]
        )
    ),

    "3M retention": True,

    "6M retention": True,

    "12M retention": True,

    "Non-placement reasons": (
        nonplacement_reason_column is not None
    ),

    "Employment attrition reasons": (
        len(attrition_transitions) > 0
    ),

    "Training-occupation relevance": (
        course_occupation_column is not None
        and occupation_column is not None
    ),

    "Wage progression": (
        len(wage_progression_table) > 0
    ),

    "Potential skill-gap analysis": (
        "occupation" in analytical_dataset.columns
    )
}

for item, available in analytics_checklist.items():

    print(
        f"{item:<40} : "
        f"{'AVAILABLE' if available else 'DATASET GAP'}"
    )