from typing import Optional, Literal
from pydantic import BaseModel, Field


class ClaimCreate(BaseModel):
    trainee_id: str
    training_id: Optional[str] = None
    outcome_type: str
    claim_date: Optional[str] = None
    effective_from: Optional[str] = None
    employer_id: Optional[str] = None
    occupation: Optional[str] = None
    location: Optional[str] = None
    reported_by: Optional[str] = "TRAINEE"


class EvidenceCreate(BaseModel):
    claim_id: str
    evidence_type: str
    source_name: str
    evidence_result: str
    evidence_date: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminUserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    created_at: str


class ClaimStatusUpdate(BaseModel):
    status: Literal["VERIFIED", "REJECTED", "FLAGGED", "PENDING"]
    remarks: Optional[str] = None


class VerificationStatusUpdate(BaseModel):
    verification_status: Literal[
        "CORROBORATED",
        "SUPPORTED",
        "REPORTED",
        "CONFLICT",
        "UNKNOWN",
        "PENDING",
    ]
    confidence_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100
    )
    remarks: Optional[str] = None


class FollowupStatusUpdate(BaseModel):
    call_status: str
    notes: Optional[str] = None


class EmploymentStatusUpdate(BaseModel):
    verification_status: Literal[
        "VERIFIED",
        "REPORTED",
        "REJECTED",
        "PENDING",
        "CONFLICT",
        "UNKNOWN",
    ]
    remarks: Optional[str] = None
