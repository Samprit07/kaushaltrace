from sqlalchemy.orm import Session

from app.models import FollowUp


VALID_CHECKPOINTS = {"3M", "6M", "12M"}


def get_checkpoint_status(
    db: Session,
    trainee_id: str,
    checkpoint: str
):
    """
    Determine the status of a trainee's follow-up checkpoint.

    OBSERVED:
        A follow-up record exists and the trainee responded.

    ATTEMPTED_NO_RESPONSE:
        A follow-up was attempted but the trainee did not respond.

    NOT_OBSERVED:
        No follow-up record exists for this checkpoint.
    """

    if checkpoint not in VALID_CHECKPOINTS:
        return {
            "checkpoint": checkpoint,
            "status": "INVALID_CHECKPOINT"
        }

    followup = (
        db.query(FollowUp)
        .filter(
            FollowUp.trainee_id == trainee_id,
            FollowUp.checkpoint == checkpoint
        )
        .order_by(FollowUp.attempt_number.desc())
        .first()
    )

    if not followup:
        return {
            "trainee_id": trainee_id,
            "checkpoint": checkpoint,
            "status": "NOT_OBSERVED"
        }

    if followup.response_status == "RESPONDED":
        return {
            "trainee_id": trainee_id,
            "checkpoint": checkpoint,
            "status": "OBSERVED",
            "outcome": followup.outcome,
            "followup_id": followup.followup_id
        }

    if followup.response_status == "NO_RESPONSE":
        return {
            "trainee_id": trainee_id,
            "checkpoint": checkpoint,
            "status": "ATTEMPTED_NO_RESPONSE",
            "followup_id": followup.followup_id
        }

    return {
        "trainee_id": trainee_id,
        "checkpoint": checkpoint,
        "status": "NOT_OBSERVED",
        "followup_id": followup.followup_id
    }