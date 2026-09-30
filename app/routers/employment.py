from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_admin, require_roles
from app.database import get_db
from app.models import EmploymentRecord, AdminUser, AdminAuditLog
from app.schemas import EmploymentStatusUpdate


router = APIRouter(
    prefix="/employment",
    tags=["Employment"]
)

admin_router = APIRouter(
    prefix="/api/employment",
    tags=["Employment Controls"]
)


@router.get("")
def get_all_employment(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin),
):
    return db.query(EmploymentRecord).all()


@router.get("/trainee/{trainee_id}")
def get_trainee_employment(
    trainee_id: str,
    db: Session = Depends(get_db)
):
    return (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.trainee_id == trainee_id
        )
        .all()
    )


@router.get("/{employment_id}")
def get_employment(
    employment_id: str,
    db: Session = Depends(get_db)
):
    record = (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.employment_id == employment_id
        )
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Employment record not found"
        )

    return record


@admin_router.patch("/{employment_id}/status")
def update_employment_status(
    employment_id: str,
    payload: EmploymentStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_roles("SUPER_ADMIN")),
):
    record = (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.employment_id == employment_id
        )
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=404,
            detail="Employment record not found"
        )

    old = {
        "verification_status": record.verification_status
    }

    record.verification_status = payload.verification_status

    db.add(
        AdminAuditLog(
            admin_user_id=current_admin.id,
            username=current_admin.username,
            action="UPDATE_EMPLOYMENT",
            entity_type="EMPLOYMENT",
            entity_id=employment_id,
            old_value=json.dumps(old),
            new_value=json.dumps({
                "verification_status":
                    payload.verification_status
            }),
            remarks=payload.remarks,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )

    db.commit()
    db.refresh(record)

    return record
