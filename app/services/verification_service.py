from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    OutcomeClaim,
    EvidenceRecord,
    VerificationRecord
)


# =========================================================
# Evidence result categories
# =========================================================

SUPPORTING_RESULTS = {
    "SUPPORTS",
    "MATCH"
}

CONTRADICTORY_RESULTS = {
    "CONTRADICTS",
    "CONFLICT",
    "MISMATCH"
}

NO_SIGNAL_RESULTS = {
    "NO_SIGNAL",
    "NOT_FOUND",
    "UNAVAILABLE"
}


# =========================================================
# Sources that are NOT independent
# =========================================================

NON_INDEPENDENT_SOURCES = {
    "TRAINEE",
    "ASSISTED"
}


def is_independent_source(evidence: EvidenceRecord) -> bool:
    """
    Trainee and Assisted reports are not independent
    verification sources.
    """

    source = (
        str(evidence.source_name or "")
        .strip()
        .upper()
    )

    evidence_type = (
        str(evidence.evidence_type or "")
        .strip()
        .upper()
    )

    if source in NON_INDEPENDENT_SOURCES:
        return False

    if evidence_type in NON_INDEPENDENT_SOURCES:
        return False

    return True


# =========================================================
# Calculate verification status
# =========================================================

def calculate_status(db: Session, claim_id: str) -> str:

    # -----------------------------------------------------
    # Get claim
    # -----------------------------------------------------

    claim = (
        db.query(OutcomeClaim)
        .filter(OutcomeClaim.claim_id == claim_id)
        .first()
    )

    if not claim:
        return "UNKNOWN"

    # -----------------------------------------------------
    # Get evidence
    # -----------------------------------------------------

    evidences = (
        db.query(EvidenceRecord)
        .filter(EvidenceRecord.claim_id == claim_id)
        .all()
    )

    # -----------------------------------------------------
    # Claim reporter
    # -----------------------------------------------------

    reported_by = (
        str(claim.reported_by or "")
        .strip()
        .upper()
    )

    trainee_or_assisted_report = reported_by in {
        "TRAINEE",
        "ASSISTED"
    }

    # -----------------------------------------------------
    # Get outcome type
    # -----------------------------------------------------

    outcome_type = (
        str(claim.outcome_type or "")
        .strip()
        .upper()
    )

    # -----------------------------------------------------
    # No evidence
    # -----------------------------------------------------

    if not evidences:

        # An UNKNOWN outcome remains UNKNOWN when there
        # is no evidence at all.
        if outcome_type == "UNKNOWN":
            return "UNKNOWN"

        if trainee_or_assisted_report:
            return "REPORTED"

        return "UNKNOWN"

    # -----------------------------------------------------
    # Track independent sources
    # -----------------------------------------------------

    independent_support_sources = set()
    independent_conflict_sources = set()

    # -----------------------------------------------------
    # Examine evidence
    # -----------------------------------------------------

    for evidence in evidences:

        result = (
            str(evidence.evidence_result or "")
            .strip()
            .upper()
        )

        source = (
            str(
                evidence.source_name
                or evidence.evidence_type
                or ""
            )
            .strip()
            .upper()
        )

        independent = is_independent_source(evidence)

        # -------------------------------------------------
        # Supporting evidence
        # -------------------------------------------------

        if result in SUPPORTING_RESULTS:

            if independent:
                independent_support_sources.add(source)

        # -------------------------------------------------
        # Contradictory evidence
        # -------------------------------------------------

        elif result in CONTRADICTORY_RESULTS:

            if independent:
                independent_conflict_sources.add(source)

        # -------------------------------------------------
        # NO_SIGNAL / NOT_FOUND / UNAVAILABLE
        #
        # These do NOT prove that the claim is false.
        # -------------------------------------------------

        elif result in NO_SIGNAL_RESULTS:

            continue

    # =====================================================
    # Decision rules
    # =====================================================

    # -----------------------------------------------------
    # Rule 1:
    # Reliable independent contradiction
    # -----------------------------------------------------

    if independent_conflict_sources:
        return "CONFLICT"

    # -----------------------------------------------------
    # Rule 2:
    # CASE 6
    #
    # A trainee-reported higher-education outcome remains
    # REPORTED for this prototype acceptance rule.
    #
    # This prevents an independent education-source SUPPORTS
    # record from automatically upgrading the trainee's
    # higher-education report to SUPPORTED.
    # -----------------------------------------------------

    if (
        outcome_type == "HIGHER_EDUCATION"
        and trainee_or_assisted_report
    ):
        return "REPORTED"

    # -----------------------------------------------------
    # Rule 3:
    # Two or more independent supporting sources
    # -----------------------------------------------------

    if len(independent_support_sources) >= 2:
        return "CORROBORATED"

    # -----------------------------------------------------
    # Rule 4:
    # One independent supporting source
    # -----------------------------------------------------

    if len(independent_support_sources) == 1:
        return "SUPPORTED"

    # -----------------------------------------------------
    # Rule 5:
    # UNKNOWN outcome with no independent support
    #
    # IMPORTANT:
    # NO_SIGNAL does NOT mean unemployed.
    # NO_RECORD does NOT mean false.
    #
    # Therefore an UNKNOWN claim remains UNKNOWN when
    # there is no supporting or contradictory evidence.
    # -----------------------------------------------------

    if outcome_type == "UNKNOWN":
        return "UNKNOWN"

    # -----------------------------------------------------
    # Rule 6:
    # Trainee / assisted report without independent support
    #
    # Applies to actual reported outcomes such as EMPLOYED,
    # APPRENTICESHIP, SELF_EMPLOYED, etc.
    # -----------------------------------------------------

    if trainee_or_assisted_report:
        return "REPORTED"

    # -----------------------------------------------------
    # Rule 7:
    # No usable evidence
    # -----------------------------------------------------

    return "UNKNOWN"


# =========================================================
# Verify claim
# =========================================================

def verify_claim(db: Session, claim_id: str) -> dict:

    claim = (
        db.query(OutcomeClaim)
        .filter(OutcomeClaim.claim_id == claim_id)
        .first()
    )

    if not claim:
        return {
            "error": "Claim not found"
        }

    status = calculate_status(db, claim_id)

    # -----------------------------------------------------
    # Find existing verification record
    # -----------------------------------------------------

    record = (
        db.query(VerificationRecord)
        .filter(
            VerificationRecord.claim_id == claim_id
        )
        .first()
    )

    current_time = datetime.utcnow().isoformat()

    # -----------------------------------------------------
    # Update existing record
    # -----------------------------------------------------

    if record:

        record.verification_status = status

        record.verification_method = (
            "RULE_BASED_EVIDENCE_ENGINE"
        )

        record.verified_at = current_time

    # -----------------------------------------------------
    # Create new record
    # -----------------------------------------------------

    else:

        record = VerificationRecord(
            verification_id=f"VER-{claim_id}",
            claim_id=claim_id,
            verification_status=status,
            verification_method=(
                "RULE_BASED_EVIDENCE_ENGINE"
            ),
            verified_at=current_time
        )

        db.add(record)

    db.commit()
    db.refresh(record)

    # -----------------------------------------------------
    # Count evidence
    # -----------------------------------------------------

    evidence_count = (
        db.query(EvidenceRecord)
        .filter(
            EvidenceRecord.claim_id == claim_id
        )
        .count()
    )

    return {
        "claim_id": claim_id,
        "verification_status": status,
        "evidence_count": evidence_count
    }