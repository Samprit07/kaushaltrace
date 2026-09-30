from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime, Boolean, Text
from app.database import Base


class Trainee(Base):
    __tablename__ = "trainees"
    trainee_id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    age_group = Column(String)
    gender = Column(String)
    education_level = Column(String)
    district = Column(String)
    consent_status = Column(String)
    consent_date = Column(String)


class Provider(Base):
    __tablename__ = "providers"
    provider_id = Column(String, primary_key=True, index=True)
    provider_name = Column(String, nullable=False)
    provider_type = Column(String)
    district = Column(String)
    state = Column(String)


class Course(Base):
    __tablename__ = "courses"
    course_id = Column(String, primary_key=True, index=True)
    course_name = Column(String, nullable=False)
    sector = Column(String)
    occupation = Column(String)
    skill_category = Column(String)


class Employer(Base):
    __tablename__ = "employers"
    employer_id = Column(String, primary_key=True, index=True)
    employer_name = Column(String, nullable=False)
    industry = Column(String)
    district = Column(String)
    state = Column(String)
    verification_status = Column(String)


class TrainingRecord(Base):
    __tablename__ = "training_records"
    training_id = Column(String, primary_key=True, index=True)
    trainee_id = Column(String, ForeignKey("trainees.trainee_id"), nullable=False, index=True)
    course_id = Column(String, ForeignKey("courses.course_id"), index=True)
    course_name = Column(String)
    provider_id = Column(String, ForeignKey("providers.provider_id"), index=True)
    provider_name = Column(String)
    scheme_id = Column(String)
    enrollment_date = Column(String)
    completion_date = Column(String)
    attendance_percentage = Column(Float)
    assessment_score = Column(Float)
    certification_status = Column(String)
    data_source = Column(String)
    verification_status = Column(String)


class OutcomeClaim(Base):
    __tablename__ = "outcome_claims"
    claim_id = Column(String, primary_key=True, index=True)
    trainee_id = Column(String, ForeignKey("trainees.trainee_id"), nullable=False, index=True)
    training_id = Column(String, ForeignKey("training_records.training_id"), index=True)
    outcome_type = Column(String)
    claim_date = Column(String)
    effective_from = Column(String)
    employer_id = Column(String, ForeignKey("employers.employer_id"), index=True)
    occupation = Column(String)
    location = Column(String)
    reported_by = Column(String)

    # Administrative workflow status. This is deliberately separate from
    # the automated verification status stored in VerificationRecord.
    status = Column(String, default="PENDING", nullable=False)
    remarks = Column(Text)
    status_updated_at = Column(String)


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"
    evidence_id = Column(String, primary_key=True, index=True)
    claim_id = Column(String, ForeignKey("outcome_claims.claim_id"), nullable=False, index=True)
    evidence_type = Column(String)
    source_name = Column(String)
    evidence_result = Column(String)
    evidence_date = Column(String)


class VerificationRecord(Base):
    __tablename__ = "verification_records"
    verification_id = Column(String, primary_key=True, index=True)
    claim_id = Column(String, ForeignKey("outcome_claims.claim_id"), nullable=False, index=True)
    verification_status = Column(String)
    verification_method = Column(String)
    verified_at = Column(String)

    # Optional human-readable confidence signal for the admin UI.
    confidence_score = Column(Float)
    override_remarks = Column(Text)


class EmploymentRecord(Base):
    __tablename__ = "employment_records"
    employment_id = Column(String, primary_key=True, index=True)
    trainee_id = Column(String, ForeignKey("trainees.trainee_id"), nullable=False, index=True)
    claim_id = Column(String, ForeignKey("outcome_claims.claim_id"), index=True)
    employer_id = Column(String, ForeignKey("employers.employer_id"), index=True)
    employer_name = Column(String)
    occupation = Column(String)
    employment_type = Column(String)
    start_date = Column(String)
    end_date = Column(String)
    data_source = Column(String)
    verification_status = Column(String)


class WageRecord(Base):
    __tablename__ = "wage_records"
    wage_id = Column(String, primary_key=True, index=True)
    trainee_id = Column(String, ForeignKey("trainees.trainee_id"), nullable=False, index=True)
    employment_id = Column(String, ForeignKey("employment_records.employment_id"), index=True)
    wage_band = Column(String)
    effective_from = Column(String)
    effective_to = Column(String)
    data_source = Column(String)
    verification_status = Column(String)


class FollowUp(Base):
    __tablename__ = "followups"
    followup_id = Column(String, primary_key=True, index=True)
    trainee_id = Column(String, ForeignKey("trainees.trainee_id"), nullable=False, index=True)
    claim_id = Column(String, ForeignKey("outcome_claims.claim_id"), index=True)
    checkpoint = Column(String)
    channel = Column(String)
    attempt_number = Column(Integer)
    response_status = Column(String)
    response_date = Column(String)
    outcome = Column(String)

    # Admin follow-up workflow fields.
    call_status = Column(String, default="PENDING")
    notes = Column(Text)


class Transition(Base):
    __tablename__ = "transitions"
    transition_id = Column(String, primary_key=True, index=True)
    trainee_id = Column(String, ForeignKey("trainees.trainee_id"), nullable=False, index=True)
    from_status = Column(String)
    to_status = Column(String)
    transition_date = Column(String)
    reason = Column(String)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="AUDITOR")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"), index=True)
    username = Column(String, index=True)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False, index=True)
    old_value = Column(Text)
    new_value = Column(Text)
    remarks = Column(Text)
    created_at = Column(DateTime, nullable=False)


class TraineeAccount(Base):
    """Login identity for a consent-based trainee portal (privacy-scoped)."""
    __tablename__ = "trainee_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    trainee_id = Column(String, ForeignKey("trainees.trainee_id"), unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)
