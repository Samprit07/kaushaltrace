from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_admin, require_roles
from app.database import get_db
from app.models import FollowUp, AdminUser, AdminAuditLog
from app.schemas import FollowupStatusUpdate
from app.services.followup_service import get_checkpoint_status


router = APIRouter(
    prefix="/followups",
    tags=["Follow-ups"]
)

admin_router = APIRouter(
    prefix="/api/followups",
    tags=["Follow-up Controls"]
)


@router.get("/{trainee_id}/{checkpoint}")
def get_followup_status(
    trainee_id: str,
    checkpoint: str,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    return get_checkpoint_status(
        db,
        trainee_id,
        checkpoint
    )


@router.get("")
def list_followups(
    db: Session = Depends(get_db),
    current_admin = Depends(get_current_admin),
):
    return db.query(FollowUp).all()


@admin_router.patch("/{followup_id}/status")
def update_followup_status(
    followup_id: str,
    payload: FollowupStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_roles("SUPER_ADMIN")),
):
    row = (
        db.query(FollowUp)
        .filter(FollowUp.followup_id == followup_id)
        .first()
    )

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Follow-up not found"
        )

    old = {
        "call_status": row.call_status,
        "notes": row.notes,
        "response_status": row.response_status,
    }

    row.call_status = payload.call_status
    row.notes = payload.notes
    row.response_status = payload.call_status

    db.add(
        AdminAuditLog(
            admin_user_id=current_admin.id,
            username=current_admin.username,
            action="UPDATE_FOLLOWUP",
            entity_type="FOLLOWUP",
            entity_id=followup_id,
            old_value=str(old),
            new_value=str({
                "call_status": payload.call_status,
                "notes": payload.notes,
            }),
            remarks=payload.notes,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )

    db.commit()
    db.refresh(row)

    return row
