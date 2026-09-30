from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_admin
from app.models import AdminUser
from app.models import (
    Trainee,
    TrainingRecord,
    OutcomeClaim,
    EmploymentRecord,
    WageRecord,
    Transition,
    VerificationRecord,
)

router = APIRouter(prefix="/trainees", tags=["Trainees"])


def _claim_with_status(db: Session, claim: OutcomeClaim) -> dict:
    ver = (
        db.query(VerificationRecord)
        .filter(VerificationRecord.claim_id == claim.claim_id)
        .first()
    )
    return {
        "claim_id": claim.claim_id,
        "trainee_id": claim.trainee_id,
        "training_id": claim.training_id,
        "outcome_type": claim.outcome_type,
        "claim_date": claim.claim_date,
        "effective_from": claim.effective_from,
        "employer_id": claim.employer_id,
        "occupation": claim.occupation,
        "location": claim.location,
        "reported_by": claim.reported_by,
        "verification_status": ver.verification_status if ver else "PENDING",
    }


@router.get("")
def list_trainees(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    """
    Enrich trainee list so the frontend can show course / centre / outcome.
    """
    trainees = db.query(Trainee).all()
    result = []

    for t in trainees:
        training = (
            db.query(TrainingRecord)
            .filter(TrainingRecord.trainee_id == t.trainee_id)
            .first()
        )
        claim = (
            db.query(OutcomeClaim)
            .filter(OutcomeClaim.trainee_id == t.trainee_id)
            .first()
        )
        ver_status = "PENDING"
        if claim:
            ver = (
                db.query(VerificationRecord)
                .filter(VerificationRecord.claim_id == claim.claim_id)
                .first()
            )
            if ver:
                ver_status = ver.verification_status

        result.append({
            "trainee_id": t.trainee_id,
            "name": t.name,
            "age_group": t.age_group,
            "gender": t.gender,
            "education_level": t.education_level,
            "district": t.district,
            "consent_status": t.consent_status,
            "consent_date": t.consent_date,
            # extras the frontend can use
            "course_name": training.course_name if training else None,
            "provider_name": training.provider_name if training else None,
            "attendance_percentage": training.attendance_percentage if training else None,
            "assessment_score": training.assessment_score if training else None,
            "outcome_type": claim.outcome_type if claim else "UNKNOWN",
            "verification_status": ver_status,
        })

    return result


@router.get("/{trainee_id}")
def get_trainee(
    trainee_id: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    trainee = db.query(Trainee).filter(Trainee.trainee_id == trainee_id).first()
    if not trainee:
        raise HTTPException(status_code=404, detail="Trainee not found")

    claims = (
        db.query(OutcomeClaim)
        .filter(OutcomeClaim.trainee_id == trainee_id)
        .all()
    )

    return {
        "trainee": trainee,
        "training_records": db.query(TrainingRecord)
            .filter(TrainingRecord.trainee_id == trainee_id)
            .all(),
        "claims": [_claim_with_status(db, c) for c in claims],
        "employment": db.query(EmploymentRecord)
            .filter(EmploymentRecord.trainee_id == trainee_id)
            .all(),
        "wages": db.query(WageRecord)
            .filter(WageRecord.trainee_id == trainee_id)
            .all(),
        "transitions": db.query(Transition)
            .filter(Transition.trainee_id == trainee_id)
            .all(),
    }
