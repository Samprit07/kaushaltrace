"""Privacy-scoped trainee portal APIs — only the logged-in trainee's data."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import Principal, require_trainee
from app.database import get_db
from app.models import (
    Trainee,
    TrainingRecord,
    OutcomeClaim,
    EmploymentRecord,
    WageRecord,
    FollowUp,
    Transition,
    VerificationRecord,
    EvidenceRecord,
)

router = APIRouter(prefix="/api/me", tags=["Trainee Portal"])


def _verification_status(db: Session, claim_id: str):
    ver = (
        db.query(VerificationRecord)
        .filter(VerificationRecord.claim_id == claim_id)
        .order_by(VerificationRecord.verified_at.desc())
        .first()
    )
    if not ver:
        return "PENDING", None
    return ver.verification_status, getattr(ver, "confidence_score", None)


@router.get("/profile")
def my_profile(
    principal: Principal = Depends(require_trainee),
    db: Session = Depends(get_db),
):
    trainee = (
        db.query(Trainee)
        .filter(Trainee.trainee_id == principal.trainee_id)
        .first()
    )
    if not trainee:
        raise HTTPException(status_code=404, detail="Trainee record not found")

    return {
        "trainee_id": trainee.trainee_id,
        "name": trainee.name,
        "age_group": trainee.age_group,
        "gender": trainee.gender,
        "education_level": trainee.education_level,
        "district": trainee.district,
        "consent_status": trainee.consent_status,
        "consent_date": trainee.consent_date,
        "username": principal.username,
    }


@router.get("/journey")
def my_journey(
    principal: Principal = Depends(require_trainee),
    db: Session = Depends(get_db),
):
    """Longitudinal personal view: training → outcome → evidence → retention signals."""
    tid = principal.trainee_id

    trainee = db.query(Trainee).filter(Trainee.trainee_id == tid).first()
    if not trainee:
        raise HTTPException(status_code=404, detail="Trainee record not found")

    training = (
        db.query(TrainingRecord)
        .filter(TrainingRecord.trainee_id == tid)
        .all()
    )
    claims = (
        db.query(OutcomeClaim).filter(OutcomeClaim.trainee_id == tid).all()
    )
    employment = (
        db.query(EmploymentRecord)
        .filter(EmploymentRecord.trainee_id == tid)
        .all()
    )
    wages = db.query(WageRecord).filter(WageRecord.trainee_id == tid).all()
    followups = db.query(FollowUp).filter(FollowUp.trainee_id == tid).all()
    transitions = (
        db.query(Transition).filter(Transition.trainee_id == tid).all()
    )

    claim_rows = []
    for c in claims:
        status, confidence = _verification_status(db, c.claim_id)
        evidence = (
            db.query(EvidenceRecord)
            .filter(EvidenceRecord.claim_id == c.claim_id)
            .all()
        )
        claim_rows.append(
            {
                "claim_id": c.claim_id,
                "outcome_type": c.outcome_type,
                "claim_date": c.claim_date,
                "occupation": c.occupation,
                "location": c.location,
                "reported_by": c.reported_by,
                "verification_status": status,
                "confidence_score": confidence,
                "evidence_count": len(evidence),
                "evidence": [
                    {
                        "evidence_type": e.evidence_type,
                        "source_name": e.source_name,
                        "evidence_result": e.evidence_result,
                        "evidence_date": e.evidence_date,
                    }
                    for e in evidence
                ],
            }
        )

    timeline = []
    for t in training:
        if t.enrollment_date:
            timeline.append(
                {
                    "date": t.enrollment_date,
                    "title": "Training enrolled",
                    "detail": t.course_name or "Training programme",
                }
            )
        if t.completion_date:
            timeline.append(
                {
                    "date": t.completion_date,
                    "title": "Training completed",
                    "detail": f"Attendance {t.attendance_percentage}% · Assessment {t.assessment_score}",
                }
            )
    for c in claim_rows:
        timeline.append(
            {
                "date": c.get("claim_date"),
                "title": "Outcome recorded",
                "detail": f"{c.get('outcome_type')} · verification {c.get('verification_status')}",
            }
        )
    for e in employment:
        timeline.append(
            {
                "date": e.start_date,
                "title": "Employment signal",
                "detail": f"{e.employer_name or 'Employer'} · {e.occupation or ''}",
            }
        )
    for f in followups:
        timeline.append(
            {
                "date": f.response_date or "",
                "title": f"Follow-up {f.checkpoint}",
                "detail": f"{f.response_status} · {f.outcome or ''}",
            }
        )

    timeline = sorted(
        [x for x in timeline if x.get("date")],
        key=lambda x: x["date"] or "",
    )

    return {
        "trainee": {
            "trainee_id": trainee.trainee_id,
            "name": trainee.name,
            "district": trainee.district,
            "consent_status": trainee.consent_status,
            "consent_date": trainee.consent_date,
            "education_level": trainee.education_level,
        },
        "training": [
            {
                "training_id": t.training_id,
                "course_name": t.course_name,
                "provider_name": t.provider_name,
                "enrollment_date": t.enrollment_date,
                "completion_date": t.completion_date,
                "attendance_percentage": t.attendance_percentage,
                "assessment_score": t.assessment_score,
                "certification_status": t.certification_status,
                "verification_status": t.verification_status,
            }
            for t in training
        ],
        "outcomes": claim_rows,
        "employment": [
            {
                "employment_id": e.employment_id,
                "employer_name": e.employer_name,
                "occupation": e.occupation,
                "employment_type": e.employment_type,
                "start_date": e.start_date,
                "end_date": e.end_date,
                "verification_status": e.verification_status,
            }
            for e in employment
        ],
        "wages": [
            {
                "wage_band": w.wage_band,
                "effective_from": w.effective_from,
                "effective_to": w.effective_to,
                "verification_status": w.verification_status,
            }
            for w in wages
        ],
        "followups": [
            {
                "checkpoint": f.checkpoint,
                "channel": f.channel,
                "response_status": f.response_status,
                "response_date": f.response_date,
                "outcome": f.outcome,
            }
            for f in followups
        ],
        "transitions": [
            {
                "from_status": t.from_status,
                "to_status": t.to_status,
                "transition_date": t.transition_date,
                "reason": t.reason,
            }
            for t in transitions
        ],
        "timeline": timeline,
        "summary": {
            "has_employment": len(employment) > 0,
            "outcome_types": list({c["outcome_type"] for c in claim_rows if c.get("outcome_type")}),
            "latest_verification": claim_rows[0]["verification_status"] if claim_rows else "PENDING",
            "followup_count": len(followups),
            "consent_status": trainee.consent_status,
        },
    }
