from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_admin,
    get_current_principal,
    get_password_hash,
    verify_password,
    Principal,
)
from app.database import get_db
from app.models import AdminUser, AdminAuditLog, Trainee, TraineeAccount


router = APIRouter(prefix="/api/auth", tags=["Authentication"])

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin@kaushaltrace2026"
TRAINEE_PASSWORD = "trainee123"

# Demo trainee logins linked to real trainee_ids
DEMO_TRAINEES = [
    {"username": "trainee1", "trainee_id": "KT0001"},
    {"username": "trainee2", "trainee_id": "KT0002"},
    {"username": "trainee3", "trainee_id": "KT0003"},
]


class LoginRequest(BaseModel):
    username: str
    password: str
    portal: Optional[str] = None  # "admin" | "trainee" | None (auto)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    kind: str
    role: str
    username: str
    full_name: str
    trainee_id: Optional[str] = None


def seed_default_admin(db: Session):
    existing = (
        db.query(AdminUser).filter(AdminUser.username == DEFAULT_USERNAME).first()
    )
    if existing:
        if not str(existing.hashed_password or "").startswith("pbkdf2_sha256$"):
            existing.hashed_password = get_password_hash(DEFAULT_PASSWORD)
            existing.role = "SUPER_ADMIN"
            existing.is_active = True
            db.commit()
        return

    db.add(
        AdminUser(
            username=DEFAULT_USERNAME,
            hashed_password=get_password_hash(DEFAULT_PASSWORD),
            full_name="KaushalTrace Administrator",
            role="SUPER_ADMIN",
            is_active=True,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    db.commit()


def seed_trainee_accounts(db: Session):
    """Create privacy-scoped trainee logins for demo IDs that exist in trainees."""
    for item in DEMO_TRAINEES:
        trainee = (
            db.query(Trainee)
            .filter(Trainee.trainee_id == item["trainee_id"])
            .first()
        )
        if not trainee:
            continue

        existing = (
            db.query(TraineeAccount)
            .filter(TraineeAccount.username == item["username"])
            .first()
        )
        if existing:
            if not str(existing.hashed_password or "").startswith("pbkdf2_sha256$"):
                existing.hashed_password = get_password_hash(TRAINEE_PASSWORD)
                existing.is_active = True
                db.commit()
            continue

        db.add(
            TraineeAccount(
                username=item["username"],
                hashed_password=get_password_hash(TRAINEE_PASSWORD),
                trainee_id=item["trainee_id"],
                full_name=trainee.name,
                is_active=True,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
    db.commit()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    password = payload.password
    portal = (payload.portal or "auto").strip().lower()

    # --- Admin path ---
    if portal in {"auto", "admin"}:
        admin = db.query(AdminUser).filter(AdminUser.username == username).first()
        if admin and verify_password(password, admin.hashed_password):
            if not admin.is_active:
                raise HTTPException(status_code=403, detail="Admin account is inactive")
            token = create_access_token(
                {"sub": admin.username, "kind": "ADMIN", "role": admin.role}
            )
            db.add(
                AdminAuditLog(
                    admin_user_id=admin.id,
                    username=admin.username,
                    action="LOGIN",
                    entity_type="AUTH",
                    entity_id=admin.username,
                    new_value="SUCCESS",
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
            )
            db.commit()
            return TokenResponse(
                access_token=token,
                kind="ADMIN",
                role=admin.role,
                username=admin.username,
                full_name=admin.full_name,
            )
        if portal == "admin":
            raise HTTPException(
                status_code=401,
                detail="Incorrect admin username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # --- Trainee path ---
    if portal in {"auto", "trainee"}:
        account = (
            db.query(TraineeAccount).filter(TraineeAccount.username == username).first()
        )
        if account and verify_password(password, account.hashed_password):
            if not account.is_active:
                raise HTTPException(status_code=403, detail="Trainee account is inactive")
            token = create_access_token(
                {
                    "sub": account.username,
                    "kind": "TRAINEE",
                    "role": "TRAINEE",
                    "trainee_id": account.trainee_id,
                }
            )
            return TokenResponse(
                access_token=token,
                kind="TRAINEE",
                role="TRAINEE",
                username=account.username,
                full_name=account.full_name,
                trainee_id=account.trainee_id,
            )
        if portal == "trainee":
            raise HTTPException(
                status_code=401,
                detail="Incorrect trainee username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

    raise HTTPException(
        status_code=401,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/me")
def me(principal: Principal = Depends(get_current_principal)):
    return {
        "kind": principal.kind,
        "username": principal.username,
        "full_name": principal.full_name,
        "role": principal.role,
        "trainee_id": principal.trainee_id,
        "admin_id": principal.admin_id,
    }


@router.post("/logout")
def logout(principal: Principal = Depends(get_current_principal)):
    return {"message": "Logged out", "username": principal.username, "kind": principal.kind}
