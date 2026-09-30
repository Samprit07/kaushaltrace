from fastapi import APIRouter, Depends
from app.auth import get_current_admin
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.database import get_db
from app.models import (
    Trainee,
    TrainingRecord,
    OutcomeClaim,
    VerificationRecord,
    EmploymentRecord,
    WageRecord,
    Course,
    Provider,
    Employer,
    FollowUp,
    Transition,
)


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
    dependencies=[Depends(get_current_admin)],
)


# ============================================================
# 1. OVERALL DASHBOARD
# ============================================================

@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    """
    Overall KaushalTrace dashboard statistics.

    This endpoint gives the frontend a quick summary of:
    - trainees
    - training records
    - outcome claims
    - employment records
    - wage records
    - verification statuses
    """

    verification_rows = (
        db.query(
            VerificationRecord.verification_status,
            func.count(VerificationRecord.verification_id)
        )
        .group_by(VerificationRecord.verification_status)
        .all()
    )

    verification_status = {
        row[0]: row[1]
        for row in verification_rows
    }

    return {
        "trainees": db.query(Trainee).count(),

        "training_records": db.query(
            TrainingRecord
        ).count(),

        "outcome_claims": db.query(
            OutcomeClaim
        ).count(),

        "employment_records": db.query(
            EmploymentRecord
        ).count(),

        "wage_records": db.query(
            WageRecord
        ).count(),

        "followups": db.query(
            FollowUp
        ).count(),

        "transitions": db.query(
            Transition
        ).count(),

        "providers": db.query(
            Provider
        ).count(),

        "courses": db.query(
            Course
        ).count(),

        "employers": db.query(
            Employer
        ).count(),

        "verification_status": verification_status
    }


# ============================================================
# 2. VERIFICATION SUMMARY
# ============================================================

@router.get("/verification")
def verification_summary(db: Session = Depends(get_db)):
    """
    Returns the number and percentage of claims in each
    verification category.
    """

    total = db.query(
        VerificationRecord
    ).count()

    rows = (
        db.query(
            VerificationRecord.verification_status,
            func.count(VerificationRecord.verification_id)
        )
        .group_by(
            VerificationRecord.verification_status
        )
        .all()
    )

    result = []

    for status, count in rows:

        percentage = 0

        if total > 0:
            percentage = round(
                (count / total) * 100,
                2
            )

        result.append({
            "status": status,
            "count": count,
            "percentage": percentage
        })

    return {
        "total_claims_verified": total,
        "statuses": result
    }


# ============================================================
# 3. COURSE OUTCOMES
# ============================================================

@router.get("/course-outcomes")
def course_outcomes(db: Session = Depends(get_db)):
    """
    Course-level outcome analytics.

    Instead of simply counting training records, this endpoint
    connects:

        Training
            ↓
        Trainee
            ↓
        Employment

    and calculates employment rate for each course.
    """

    courses = (
        db.query(
            TrainingRecord.course_id,
            TrainingRecord.course_name,
            func.count(
                func.distinct(
                    TrainingRecord.trainee_id
                )
            ).label("trainee_count")
        )
        .group_by(
            TrainingRecord.course_id,
            TrainingRecord.course_name
        )
        .all()
    )

    result = []

    for course in courses:

        trainee_ids = (
            db.query(
                TrainingRecord.trainee_id
            )
            .filter(
                TrainingRecord.course_id
                == course.course_id
            )
            .distinct()
            .all()
        )

        trainee_id_list = [
            row[0]
            for row in trainee_ids
        ]

        employed_count = 0

        if trainee_id_list:

            employed_count = (
                db.query(
                    func.count(
                        func.distinct(
                            EmploymentRecord.trainee_id
                        )
                    )
                )
                .filter(
                    EmploymentRecord.trainee_id.in_(
                        trainee_id_list
                    )
                )
                .scalar()
                or 0
            )

        employment_rate = 0

        if course.trainee_count > 0:
            employment_rate = round(
                (
                    employed_count
                    / course.trainee_count
                ) * 100,
                2
            )

        result.append({
            "course_id": course.course_id,
            "course_name": course.course_name,
            "trainee_count": course.trainee_count,
            "employed_count": employed_count,
            "employment_rate": employment_rate
        })

    return result


# ============================================================
# 4. PROVIDER PERFORMANCE
# ============================================================

@router.get("/provider-performance")
def provider_performance(db: Session = Depends(get_db)):
    """
    Measures training-provider performance.

    Metrics:
    - trainees trained
    - employed trainees
    - employment rate
    """

    providers = (
        db.query(
            TrainingRecord.provider_id,
            TrainingRecord.provider_name,
            func.count(
                func.distinct(
                    TrainingRecord.trainee_id
                )
            ).label("trainee_count")
        )
        .group_by(
            TrainingRecord.provider_id,
            TrainingRecord.provider_name
        )
        .all()
    )

    result = []

    for provider in providers:

        trainee_ids = (
            db.query(
                TrainingRecord.trainee_id
            )
            .filter(
                TrainingRecord.provider_id
                == provider.provider_id
            )
            .distinct()
            .all()
        )

        trainee_id_list = [
            row[0]
            for row in trainee_ids
        ]

        employed_count = 0

        if trainee_id_list:

            employed_count = (
                db.query(
                    func.count(
                        func.distinct(
                            EmploymentRecord.trainee_id
                        )
                    )
                )
                .filter(
                    EmploymentRecord.trainee_id.in_(
                        trainee_id_list
                    )
                )
                .scalar()
                or 0
            )

        employment_rate = 0

        if provider.trainee_count > 0:
            employment_rate = round(
                (
                    employed_count
                    / provider.trainee_count
                ) * 100,
                2
            )

        result.append({
            "provider_id": provider.provider_id,
            "provider_name": provider.provider_name,
            "trainee_count": provider.trainee_count,
            "employed_count": employed_count,
            "employment_rate": employment_rate
        })

    return result


# ============================================================
# 5. EMPLOYMENT OUTCOMES
# ============================================================

@router.get("/employment")
def employment_outcomes(db: Session = Depends(get_db)):
    """
    Overall employment outcome statistics.
    """

    total_trainees = db.query(
        Trainee
    ).count()

    employed_trainees = db.query(
        func.count(
            func.distinct(
                EmploymentRecord.trainee_id
            )
        )
    ).scalar() or 0

    verified_employment = db.query(
        func.count(
            func.distinct(
                EmploymentRecord.trainee_id
            )
        )
    ).filter(
        EmploymentRecord.verification_status
        == "VERIFIED"
    ).scalar() or 0

    reported_employment = db.query(
        func.count(
            func.distinct(
                EmploymentRecord.trainee_id
            )
        )
    ).filter(
        EmploymentRecord.verification_status
        == "REPORTED"
    ).scalar() or 0

    employment_rate = 0

    if total_trainees > 0:
        employment_rate = round(
            (
                employed_trainees
                / total_trainees
            ) * 100,
            2
        )

    return {
        "total_trainees": total_trainees,
        "employed_trainees": employed_trainees,
        "verified_employment_trainees": verified_employment,
        "reported_employment_trainees": reported_employment,
        "employment_rate": employment_rate
    }


# ============================================================
# 6. EMPLOYMENT BY TYPE
# ============================================================

@router.get("/employment-by-type")
def employment_by_type(db: Session = Depends(get_db)):
    """
    Breaks employment outcomes into employment types.

    Example:
    - Full-time
    - Part-time
    - Apprenticeship
    - Self-employment
    """

    rows = (
        db.query(
            EmploymentRecord.employment_type,
            func.count(
                EmploymentRecord.employment_id
            )
        )
        .group_by(
            EmploymentRecord.employment_type
        )
        .all()
    )

    return [
        {
            "employment_type": row[0],
            "count": row[1]
        }
        for row in rows
    ]


# ============================================================
# 7. WAGE DISTRIBUTION
# ============================================================

@router.get("/wages")
def wage_distribution(db: Session = Depends(get_db)):
    """
    Shows distribution of trainees across wage bands.
    """

    rows = (
        db.query(
            WageRecord.wage_band,
            func.count(
                WageRecord.wage_id
            )
        )
        .group_by(
            WageRecord.wage_band
        )
        .all()
    )

    total = sum(
        row[1]
        for row in rows
    )

    result = []

    for wage_band, count in rows:

        percentage = 0

        if total > 0:
            percentage = round(
                (count / total) * 100,
                2
            )

        result.append({
            "wage_band": wage_band,
            "count": count,
            "percentage": percentage
        })

    return {
        "total_wage_records": total,
        "distribution": result
    }


# ============================================================
# 8. INDUSTRY / EMPLOYER OUTCOMES
# ============================================================

@router.get("/industry-outcomes")
def industry_outcomes(db: Session = Depends(get_db)):
    """
    Groups employment outcomes by employer industry.
    """

    rows = (
        db.query(
            Employer.industry,
            func.count(
                func.distinct(
                    EmploymentRecord.trainee_id
                )
            ).label("trainee_count")
        )
        .join(
            EmploymentRecord,
            EmploymentRecord.employer_id
            == Employer.employer_id
        )
        .group_by(
            Employer.industry
        )
        .all()
    )

    return [
        {
            "industry": row[0],
            "trainee_count": row[1]
        }
        for row in rows
    ]


# ============================================================
# 9. EMPLOYMENT BY LOCATION
# ============================================================

@router.get("/location-outcomes")
def location_outcomes(db: Session = Depends(get_db)):
    """
    Shows where employment outcomes are occurring.
    """

    rows = (
        db.query(
            EmploymentRecord.employer_name,
            func.count(
                func.distinct(
                    EmploymentRecord.trainee_id
                )
            )
        )
        .group_by(
            EmploymentRecord.employer_name
        )
        .order_by(
            func.count(
                func.distinct(
                    EmploymentRecord.trainee_id
                )
            ).desc()
        )
        .all()
    )

    return [
        {
            "employer": row[0],
            "trainee_count": row[1]
        }
        for row in rows
    ]


# ============================================================
# 10. TRAINING VERIFICATION
# ============================================================

@router.get("/training-verification")
def training_verification(db: Session = Depends(get_db)):
    """
    Shows training-record verification status.
    """

    rows = (
        db.query(
            TrainingRecord.verification_status,
            func.count(
                TrainingRecord.training_id
            )
        )
        .group_by(
            TrainingRecord.verification_status
        )
        .all()
    )

    return [
        {
            "verification_status": row[0],
            "count": row[1]
        }
        for row in rows
    ]


# ============================================================
# 11. EMPLOYMENT VERIFICATION
# ============================================================

@router.get("/employment-verification")
def employment_verification(db: Session = Depends(get_db)):
    """
    Shows employment-record verification status.
    """

    rows = (
        db.query(
            EmploymentRecord.verification_status,
            func.count(
                EmploymentRecord.employment_id
            )
        )
        .group_by(
            EmploymentRecord.verification_status
        )
        .all()
    )

    return [
        {
            "verification_status": row[0],
            "count": row[1]
        }
        for row in rows
    ]


# ============================================================
# 12. FOLLOW-UP ANALYTICS
# ============================================================

@router.get("/followups")
def followup_analytics(db: Session = Depends(get_db)):
    """
    Shows follow-up response statistics.
    """

    total = db.query(
        FollowUp
    ).count()

    rows = (
        db.query(
            FollowUp.response_status,
            func.count(
                FollowUp.followup_id
            )
        )
        .group_by(
            FollowUp.response_status
        )
        .all()
    )

    response_distribution = [
        {
            "response_status": row[0],
            "count": row[1]
        }
        for row in rows
    ]

    return {
        "total_followups": total,
        "response_distribution": response_distribution
    }


# ============================================================
# 13. TRANSITIONS
# ============================================================

@router.get("/transitions")
def transition_analytics(db: Session = Depends(get_db)):
    """
    Shows movement between trainee statuses.

    Example:

        TRAINED → EMPLOYED
        EMPLOYED → JOB_CHANGE
        TRAINED → HIGHER_EDUCATION
    """

    rows = (
        db.query(
            Transition.from_status,
            Transition.to_status,
            func.count(
                Transition.transition_id
            )
        )
        .group_by(
            Transition.from_status,
            Transition.to_status
        )
        .all()
    )

    return [
        {
            "from_status": row[0],
            "to_status": row[1],
            "count": row[2]
        }
        for row in rows
    ]


# ============================================================
# 14. COURSE → EMPLOYMENT ALIGNMENT
# ============================================================

@router.get("/course-employment-alignment")
def course_employment_alignment(
    db: Session = Depends(get_db)
):
    """
    Compares the occupation taught in a course with the
    occupation in the trainee's employment record.

    Classification:

        ALIGNED
        RELATED
        UNRELATED
        UNKNOWN

    IMPORTANT:
    UNRELATED is only an analytical signal.
    It must NOT automatically be interpreted as SKILL_GAP.
    """

    records = (
        db.query(
            TrainingRecord.trainee_id,
            TrainingRecord.course_id,
            TrainingRecord.course_name,
            Course.occupation,
            EmploymentRecord.occupation.label(
                "employment_occupation"
            )
        )
        .join(
            Course,
            TrainingRecord.course_id
            == Course.course_id
        )
        .join(
            OutcomeClaim,
            OutcomeClaim.training_id
            == TrainingRecord.training_id
        )
        .join(
            EmploymentRecord,
            EmploymentRecord.claim_id
            == OutcomeClaim.claim_id
        )
        .all()
    )

    aligned = 0
    related = 0
    unrelated = 0
    unknown = 0

    # Transparent rule-based occupation grouping.
    #
    # These groups are deliberately small and explainable
    # for the prototype. They are NOT an ML skill-gap model.

    occupation_groups = {
        "electrician": "electrical",
        "solar pv installer": "electrical",
        "welder": "manufacturing",
        "data entry operator": "digital",
        "sales associate": "retail",
        "healthcare assistant": "healthcare",
        "beauty therapist": "beauty",
        "food processing operator": "food_processing",
    }

    for record in records:

        trained_occupation = (
            record.occupation
            or ""
        ).strip().lower()

        employed_occupation = (
            record.employment_occupation
            or ""
        ).strip().lower()

        # Missing information
        if not trained_occupation or not employed_occupation:
            unknown += 1
            continue

        # Exact occupation match
        if trained_occupation == employed_occupation:
            aligned += 1
            continue

        trained_group = occupation_groups.get(
            trained_occupation
        )

        employed_group = occupation_groups.get(
            employed_occupation
        )

        # Same occupational group, but different occupation
        if (
            trained_group
            and employed_group
            and trained_group == employed_group
        ):
            related += 1

        # Different occupational groups
        else:
            unrelated += 1

    total = (
        aligned
        + related
        + unrelated
        + unknown
    )

    alignment_rate = 0

    if total > 0:
        alignment_rate = round(
            (
                (aligned + related)
                / total
            ) * 100,
            2
        )

    return {
        "total_records": total,
        "aligned": aligned,
        "related": related,
        "unrelated": unrelated,
        "unknown": unknown,
        "alignment_rate": alignment_rate
    }


# ============================================================
# 15. TRAINEE OUTCOME SUMMARY
# ============================================================

@router.get("/trainee/{trainee_id}")
def trainee_outcome_summary(
    trainee_id: str,
    db: Session = Depends(get_db)
):
    """
    Gives a compact analytical summary for one trainee.
    """

    trainee = (
        db.query(Trainee)
        .filter(
            Trainee.trainee_id
            == trainee_id
        )
        .first()
    )

    if not trainee:

        return {
            "error": "Trainee not found"
        }

    training_count = db.query(
        TrainingRecord
    ).filter(
        TrainingRecord.trainee_id
        == trainee_id
    ).count()

    claim_count = db.query(
        OutcomeClaim
    ).filter(
        OutcomeClaim.trainee_id
        == trainee_id
    ).count()

    employment_count = db.query(
        EmploymentRecord
    ).filter(
        EmploymentRecord.trainee_id
        == trainee_id
    ).count()

    wage_count = db.query(
        WageRecord
    ).filter(
        WageRecord.trainee_id
        == trainee_id
    ).count()

    transition_count = db.query(
        Transition
    ).filter(
        Transition.trainee_id
        == trainee_id
    ).count()

    followup_count = db.query(
        FollowUp
    ).filter(
        FollowUp.trainee_id
        == trainee_id
    ).count()

    return {
        "trainee_id": trainee_id,
        "name": trainee.name,
        "training_records": training_count,
        "outcome_claims": claim_count,
        "employment_records": employment_count,
        "wage_records": wage_count,
        "followups": followup_count,
        "transitions": transition_count,
        "has_employment": employment_count > 0
    }

# ============================================================
# PANDAS ANALYTICS ENGINE (from offline main.py pipeline)
# ============================================================

from app.services.analytics_engine import (
    programme_summary,
    retention_summary,
    calculate_retention,
    wage_progression,
    provider_performance,
    progression_signals,
    outcomes_by_course,
)


@router.get("/programme-summary")
def api_programme_summary():
    """Overall programme KPIs from the analytical dataset."""
    return programme_summary()


@router.get("/retention-summary")
def api_retention_summary():
    """3M / 6M / 12M employment retention among observed follow-ups."""
    return retention_summary()


@router.get("/retention/{checkpoint}")
def api_retention_checkpoint(checkpoint: str):
    """Single checkpoint retention (3M, 6M, or 12M)."""
    cp = checkpoint.upper()
    if cp not in {"3M", "6M", "12M"}:
        return {"error": "checkpoint must be 3M, 6M, or 12M"}
    return calculate_retention(cp)


@router.get("/wage-progression")
def api_wage_progression():
    """Wage-band progression for trainees with multiple wage records."""
    return wage_progression()


@router.get("/provider-attention")
def api_provider_attention():
    """Provider performance with attention levels from the analytics pipeline."""
    return provider_performance()


@router.get("/progression-signals")
def api_progression_signals():
    """Live values for Analytics page progression cards."""
    return progression_signals()


@router.get("/course-outcome-rates")
def api_course_outcome_rates():
    """Employment rates by course from the analytical dataset."""
    return outcomes_by_course()


# ============================================================
# DIMENSIONAL BREAKDOWNS (region / course / employer)
# ============================================================

@router.get("/by-district")
def analytics_by_district(db: Session = Depends(get_db)):
    """Trainees and positive outcomes by district/region."""
    trainees = db.query(Trainee).all()
    claims = db.query(OutcomeClaim).all()
    employment = db.query(EmploymentRecord).all()

    by_district = {}
    for t in trainees:
        d = t.district or "UNKNOWN"
        row = by_district.setdefault(
            d,
            {"district": d, "trainees": 0, "with_claim": 0, "employed_signal": 0, "positive_outcomes": 0},
        )
        row["trainees"] += 1

    claim_by_trainee = {}
    for c in claims:
        claim_by_trainee.setdefault(c.trainee_id, []).append(c)

    employed_ids = {e.trainee_id for e in employment}
    positive = {"EMPLOYED", "SELF_EMPLOYED", "APPRENTICESHIP", "HIGHER_EDUCATION"}

    trainee_district = {t.trainee_id: (t.district or "UNKNOWN") for t in trainees}
    for tid, clist in claim_by_trainee.items():
        d = trainee_district.get(tid, "UNKNOWN")
        if d not in by_district:
            continue
        by_district[d]["with_claim"] += 1
        if any((c.outcome_type or "").upper() in positive for c in clist):
            by_district[d]["positive_outcomes"] += 1
        if tid in employed_ids:
            by_district[d]["employed_signal"] += 1

    rows = list(by_district.values())
    for r in rows:
        n = r["trainees"] or 1
        r["placement_rate"] = round(r["positive_outcomes"] / n * 100, 1)
        r["employment_signal_rate"] = round(r["employed_signal"] / n * 100, 1)
    rows.sort(key=lambda x: x["trainees"], reverse=True)
    return rows


@router.get("/by-course")
def analytics_by_course(db: Session = Depends(get_db)):
    """Training volume and placement signals by course."""
    trainings = db.query(TrainingRecord).all()
    claims = db.query(OutcomeClaim).all()
    employment = db.query(EmploymentRecord).all()

    by_course = {}
    trainee_courses = {}
    for tr in trainings:
        key = tr.course_name or tr.course_id or "UNKNOWN"
        row = by_course.setdefault(
            key,
            {
                "course_name": key,
                "trainees": 0,
                "completed": 0,
                "positive_outcomes": 0,
                "employed_signal": 0,
            },
        )
        row["trainees"] += 1
        if tr.completion_date:
            row["completed"] += 1
        trainee_courses.setdefault(tr.trainee_id, set()).add(key)

    positive = {"EMPLOYED", "SELF_EMPLOYED", "APPRENTICESHIP", "HIGHER_EDUCATION"}
    employed_ids = {e.trainee_id for e in employment}
    for c in claims:
        courses = trainee_courses.get(c.trainee_id, [])
        for key in courses:
            if (c.outcome_type or "").upper() in positive:
                by_course[key]["positive_outcomes"] += 1
            if c.trainee_id in employed_ids:
                by_course[key]["employed_signal"] += 1

    # Fix double-counting employed_signal: recount uniquely per course
    for key, row in by_course.items():
        tids = [tid for tid, cs in trainee_courses.items() if key in cs]
        row["employed_signal"] = sum(1 for tid in tids if tid in employed_ids)
        pos_trainees = set()
        for c in claims:
            if c.trainee_id in tids and (c.outcome_type or "").upper() in positive:
                pos_trainees.add(c.trainee_id)
        row["positive_outcomes"] = len(pos_trainees)
        n = row["trainees"] or 1
        row["completion_rate"] = round(row["completed"] / n * 100, 1)
        row["placement_rate"] = round(row["positive_outcomes"] / n * 100, 1)

    rows = list(by_course.values())
    rows.sort(key=lambda x: x["trainees"], reverse=True)
    return rows


@router.get("/by-employer")
def analytics_by_employer(db: Session = Depends(get_db)):
    """Employers linked to employment / training outcome signals."""
    employment = db.query(EmploymentRecord).all()
    by_emp = {}
    for e in employment:
        key = e.employer_name or e.employer_id or "UNKNOWN"
        row = by_emp.setdefault(
            key,
            {
                "employer_name": key,
                "placements": 0,
                "trainees": set(),
                "occupations": set(),
                "verified": 0,
            },
        )
        row["placements"] += 1
        row["trainees"].add(e.trainee_id)
        if e.occupation:
            row["occupations"].add(e.occupation)
        if (e.verification_status or "").upper() in {"VERIFIED", "SUPPORTED", "CORROBORATED"}:
            row["verified"] += 1

    rows = []
    for row in by_emp.values():
        rows.append(
            {
                "employer_name": row["employer_name"],
                "placements": row["placements"],
                "unique_trainees": len(row["trainees"]),
                "verified_records": row["verified"],
                "sample_occupations": ", ".join(sorted(row["occupations"])[:3]) or "—",
            }
        )
    rows.sort(key=lambda x: x["placements"], reverse=True)
    return rows


@router.get("/impact-matrix")
def analytics_impact_matrix(db: Session = Depends(get_db)):
    """Single payload for admin impact filters: district, course, employer."""
    return {
        "by_district": analytics_by_district(db),
        "by_course": analytics_by_course(db),
        "by_employer": analytics_by_employer(db),
    }


# ============================================================
# CSV export (source datasets for offline / category analysis)
# ============================================================

from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

_CSV_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "csv"

_ALLOWED_CSV = {
    "trainees.csv",
    "training_records.csv",
    "outcome_claims.csv",
    "employment_records.csv",
    "wage_records.csv",
    "verification_records.csv",
    "evidence_records.csv",
    "followups.csv",
    "transitions.csv",
    "providers.csv",
    "courses.csv",
    "employers.csv",
}


@router.get("/csv")
def list_csv_files():
    """List available CSV source files for admin analytics export."""
    files = []
    if _CSV_DIR.exists():
        for name in sorted(_ALLOWED_CSV):
            path = _CSV_DIR / name
            if path.is_file():
                files.append(
                    {
                        "file": name,
                        "category": name.replace(".csv", ""),
                        "size_bytes": path.stat().st_size,
                    }
                )
    return {"files": files, "count": len(files)}


@router.get("/csv/{file_name}")
def download_csv_file(file_name: str):
    """
    Download or stream a source CSV by category filename.
    Used by admin Analytics Overview / Deep Analytics for copy & download.
    """
    safe = Path(file_name).name
    if safe not in _ALLOWED_CSV:
        raise HTTPException(status_code=404, detail="CSV category not found")
    path = _CSV_DIR / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail="CSV file missing on server")
    return FileResponse(
        path=str(path),
        media_type="text/csv",
        filename=safe,
        headers={"Cache-Control": "no-store"},
    )
