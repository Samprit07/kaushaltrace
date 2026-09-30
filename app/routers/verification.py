import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_admin, require_roles
from app.database import get_db
from app.models import (
    AdminAuditLog,
    AdminUser,
    VerificationRecord,
)
from app.schemas import VerificationStatusUpdate


router = APIRouter(
    prefix="/api/verification",
    tags=["Verification Controls"]
)


@router.get("/{record_id}")
def get_verification(
    record_id: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    record = (
        db.query(VerificationRecord)
        .filter(
            VerificationRecord.verification_id == record_id
        )
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Verification record not found"
        )

    return record


@router.patch("/{record_id}/status")
def update_verification_status(
    record_id: str,
    payload: VerificationStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_roles("SUPER_ADMIN")),
):
    record = (
        db.query(VerificationRecord)
        .filter(
            VerificationRecord.verification_id == record_id
        )
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Verification record not found"
        )

    old = {
        "verification_status": record.verification_status,
        "confidence_score": record.confidence_score,
        "override_remarks": record.override_remarks,
    }

    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    record.verification_status = payload.verification_status
    record.confidence_score = payload.confidence_score
    record.override_remarks = payload.remarks
    record.verification_method = "ADMIN_OVERRIDE"
    record.verified_at = now

    db.add(
        AdminAuditLog(
            admin_user_id=current_admin.id,
            username=current_admin.username,
            action="UPDATE_VERIFICATION",
            entity_type="VERIFICATION",
            entity_id=record_id,
            old_value=json.dumps(old, default=str),
            new_value=json.dumps({
                "verification_status": payload.verification_status,
                "confidence_score": payload.confidence_score,
                "override_remarks": payload.remarks,
            }),
            remarks=payload.remarks,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )

    db.commit()
    db.refresh(record)

    return record
