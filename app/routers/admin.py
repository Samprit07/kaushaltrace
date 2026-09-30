from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_admin
from app.database import get_db
from app.models import AdminAuditLog, AdminUser


router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"]
)


@router.get("/audit-log")
def audit_log(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    limit = max(1, min(limit, 250))

    rows = (
        db.query(AdminAuditLog)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": row.id,
            "username": row.username,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "old_value": row.old_value,
            "new_value": row.new_value,
            "remarks": row.remarks,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]
