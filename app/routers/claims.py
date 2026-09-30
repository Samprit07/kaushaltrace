import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_admin, require_roles
from app.database import get_db
from app.models import (
    AdminAuditLog,
    AdminUser,
    OutcomeClaim,
    EvidenceRecord,
    VerificationRecord,
)
from app.schemas import (
    ClaimCreate,
    ClaimStatusUpdate,
    EvidenceCreate,
)
from app.services.verification_service import verify_claim


router = APIRouter(
    prefix="/claims",
    tags=["Outcome Claims"]
)

admin_router = APIRouter(
    prefix="/api/claims",
    tags=["Admin Claim Controls"]
)


def _audit(
    db: Session,
    admin: AdminUser,
    action: str,
    entity_type: str,
    entity_id: str,
    old_value=None,
    new_value=None,
    remarks=None,
):
    db.add(
        AdminAuditLog(
            admin_user_id=admin.id,
            username=admin.username,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=json.dumps(old_value, default=str)
            if old_value is not None else None,
            new_value=json.dumps(new_value, default=str)
            if new_value is not None else None,
            remarks=remarks,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )


@router.get("")
def list_claims(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    claims = db.query(OutcomeClaim).all()
    result = []

    for claim in claims:
        ver = (
            db.query(VerificationRecord)
            .filter(
                VerificationRecord.claim_id == claim.claim_id
            )
            .order_by(VerificationRecord.verified_at.desc())
            .first()
        )

        result.append({
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
            "status": claim.status or "PENDING",
            "remarks": claim.remarks,
            "status_updated_at": claim.status_updated_at,
            "verification_status": (
                ver.verification_status if ver else "PENDING"
            ),
            "confidence_score": (
                ver.confidence_score if ver else None
            ),
        })

    return result


@router.get("/{claim_id}")
def get_claim(
    claim_id: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    claim = (
        db.query(OutcomeClaim)
        .filter(OutcomeClaim.claim_id == claim_id)
        .first()
    )

    if not claim:
        raise HTTPException(
            status_code=404,
            detail="Claim not found"
        )

    return {
        "claim": claim,
        "evidence": (
            db.query(EvidenceRecord)
            .filter(EvidenceRecord.claim_id == claim_id)
            .all()
        ),
        "verification": (
            db.query(VerificationRecord)
            .filter(VerificationRecord.claim_id == claim_id)
            .order_by(VerificationRecord.verified_at.desc())
            .all()
        )
    }


@router.post("")
def create_claim(
    payload: ClaimCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_roles("SUPER_ADMIN")),
):
    count = db.query(OutcomeClaim).count() + 1

    claim = OutcomeClaim(
        claim_id=f"API{count:04d}",
        status="PENDING",
        **payload.model_dump()
    )

    db.add(claim)

    _audit(
        db,
        current_admin,
        "CREATE",
        "CLAIM",
        claim.claim_id,
        new_value=payload.model_dump(),
    )

    db.commit()
    db.refresh(claim)

    return claim


@router.post("/{claim_id}/verify")
def verify(
    claim_id: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_roles("SUPER_ADMIN")),
):
    result = verify_claim(
        db,
        claim_id
    )

    if "error" in result:
        raise HTTPException(
            status_code=404,
            detail=result["error"]
        )

    _audit(
        db,
        current_admin,
        "AUTO_VERIFY",
        "CLAIM",
        claim_id,
        new_value=result,
    )
    db.commit()

    return result


@router.post("/{claim_id}/evidence")
def add_evidence(
    claim_id: str,
    payload: EvidenceCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_roles("SUPER_ADMIN")),
):
    claim = (
        db.query(OutcomeClaim)
        .filter(OutcomeClaim.claim_id == claim_id)
        .first()
    )

    if not claim:
        raise HTTPException(
            status_code=404,
            detail="Claim not found"
        )

    evidence = EvidenceRecord(
        evidence_id=(
            f"EVD-{claim_id}-"
            f"{db.query(EvidenceRecord).count() + 1}"
        ),
        claim_id=claim_id,
        evidence_type=payload.evidence_type,
        source_name=payload.source_name,
        evidence_result=payload.evidence_result,
        evidence_date=payload.evidence_date
    )

    db.add(evidence)

    _audit(
        db,
        current_admin,
        "ADD_EVIDENCE",
        "CLAIM",
        claim_id,
        new_value=payload.model_dump(),
    )

    db.commit()
    db.refresh(evidence)

    return evidence


@admin_router.patch("/{claim_id}/status")
def update_claim_status(
    claim_id: str,
    payload: ClaimStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_roles("SUPER_ADMIN")),
):
    claim = (
        db.query(OutcomeClaim)
        .filter(OutcomeClaim.claim_id == claim_id)
        .first()
    )

    if not claim:
        raise HTTPException(
            status_code=404,
            detail="Claim not found"
        )

    old = {
        "status": claim.status,
        "remarks": claim.remarks,
        "status_updated_at": claim.status_updated_at,
    }

    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    claim.status = payload.status
    claim.remarks = payload.remarks
    claim.status_updated_at = now

    _audit(
        db,
        current_admin,
        "UPDATE_STATUS",
        "CLAIM",
        claim_id,
        old_value=old,
        new_value={
            "status": payload.status,
            "remarks": payload.remarks,
            "status_updated_at": now,
        },
        remarks=payload.remarks,
    )

    db.commit()
    db.refresh(claim)

    return {
        "claim_id": claim.claim_id,
        "status": claim.status,
        "remarks": claim.remarks,
        "status_updated_at": claim.status_updated_at,
    }
