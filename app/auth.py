"""
JWT authentication for KaushalTrace.

Supports two separate identity types:
  - ADMIN  (AdminUser)  → programme intelligence & controls
  - TRAINEE (TraineeAccount) → privacy-scoped personal outcomes only

Stdlib HMAC-SHA256 JWT + PBKDF2 (no jose/passlib required).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AdminUser, TraineeAccount

SECRET_KEY = os.getenv(
    "KAUSHALTRACE_SECRET_KEY",
    "CHANGE_THIS_DEVELOPMENT_SECRET_BEFORE_PRODUCTION",
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("KAUSHALTRACE_ACCESS_TOKEN_MINUTES", "120")
)

security = HTTPBearer(auto_error=False)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def get_password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
    )
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    if hashed_password.startswith("pbkdf2_sha256$"):
        try:
            _, salt, digest_hex = hashed_password.split("$", 2)
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt.encode("utf-8"),
                120_000,
            )
            return hmac.compare_digest(digest.hex(), digest_hex)
        except Exception:
            return False
    try:
        from passlib.context import CryptContext

        ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return ctx.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    header = {"alg": ALGORITHM, "typ": "JWT"}
    payload = dict(data)
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload["exp"] = int(expire.timestamp())
    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{h}.{p}".encode("ascii")
    sig = hmac.new(SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url_encode(sig)}"


def decode_access_token(token: str) -> dict:
    try:
        h, p, s = token.split(".")
        signing_input = f"{h}.{p}".encode("ascii")
        expected = hmac.new(
            SECRET_KEY.encode("utf-8"), signing_input, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_b64url_encode(expected), s):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature",
                headers={"WWW-Authenticate": "Bearer"},
            )
        payload = json.loads(_b64url_decode(p).decode("utf-8"))
        exp = payload.get("exp")
        if exp is not None and datetime.now(timezone.utc).timestamp() > float(exp):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


@dataclass
class Principal:
    """Unified auth principal for admin or trainee sessions."""

    kind: str  # ADMIN | TRAINEE
    username: str
    full_name: str
    role: str
    trainee_id: Optional[str] = None
    admin_id: Optional[int] = None


def get_current_principal(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Principal:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    username = payload.get("sub")
    kind = str(payload.get("kind") or payload.get("role") or "").upper()
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Prefer explicit kind; fall back to ADMIN for legacy tokens
    if kind == "TRAINEE" or payload.get("trainee_id"):
        account = (
            db.query(TraineeAccount)
            .filter(TraineeAccount.username == username)
            .first()
        )
        if not account or not account.is_active:
            raise HTTPException(status_code=401, detail="Trainee account inactive or missing")
        return Principal(
            kind="TRAINEE",
            username=account.username,
            full_name=account.full_name,
            role="TRAINEE",
            trainee_id=account.trainee_id,
        )

    admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if not admin or not admin.is_active:
        raise HTTPException(status_code=401, detail="Admin account inactive or missing")
    return Principal(
        kind="ADMIN",
        username=admin.username,
        full_name=admin.full_name,
        role=admin.role,
        admin_id=admin.id,
    )


def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> AdminUser:
    """Admin-only dependency (used by existing admin routes)."""
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    username = payload.get("sub")
    kind = str(payload.get("kind") or "").upper()
    if kind == "TRAINEE":
        raise HTTPException(status_code=403, detail="Admin access required")
    admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if not admin or not admin.is_active:
        raise HTTPException(status_code=401, detail="Could not validate admin credentials")
    return admin


def require_roles(*allowed_roles: str):
    allowed = {role.upper() for role in allowed_roles}

    def dependency(current_admin: AdminUser = Depends(get_current_admin)) -> AdminUser:
        if current_admin.role.upper() not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient admin permissions",
            )
        return current_admin

    return dependency


def require_trainee(
    principal: Principal = Depends(get_current_principal),
) -> Principal:
    if principal.kind != "TRAINEE" or not principal.trainee_id:
        raise HTTPException(status_code=403, detail="Trainee access required")
    return principal
