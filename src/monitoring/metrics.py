from sqlalchemy import select, func
from sqlalchemy.orm import Session

from src.models.pipeline_run import PipelineRun
from src.models.charging_session import ChargingSession


def calculate_percentage(count: int, total: int) -> float:
    """
    Calculate the percentage of a particular record category.
    Returns 0.0 when there are no input records.
    """
    if total == 0:
        return 0.0

    return round((count / total) * 100, 2)


def calculate_run_metrics(db_session: Session, run_id: str) -> dict:
    """
    Calculate monitoring metrics for a pipeline run.

    Metrics include:
    - Input, accepted, rejected and duplicate records
    - Anomalous charging sessions
    - Processing duration
    - Acceptance, rejection and duplicate percentages
    """

    # Fetch the pipeline run.
    pipeline_run = db_session.get(PipelineRun, run_id)

    if pipeline_run is None:
        raise ValueError(f"Pipeline run {run_id} does not exist")

    # Retrieve record counts from the pipeline run.
    input_count = pipeline_run.input_count
    accepted_count = pipeline_run.accepted_count
    rejected_count = pipeline_run.rejected_count
    duplicate_count = pipeline_run.duplicate_count

    # Count anomalous sessions last processed by this run.
    anomalous_session_count = db_session.scalar(
        select(func.count())
        .select_from(ChargingSession)
        .where(
            ChargingSession.last_processed_run_id == run_id,
            ChargingSession.session_status == "ANOMALOUS"
        )
    )

    # Calculate processing duration.
    processing_duration_seconds = None

    if pipeline_run.completed_at is not None:
        processing_duration_seconds = round(
            (
                pipeline_run.completed_at - pipeline_run.started_at
            ).total_seconds(),
            3
        )

    # Calculate record percentages.
    acceptance_rate = calculate_percentage(
        accepted_count,
        input_count
    )

    rejection_rate = calculate_percentage(
        rejected_count,
        input_count
    )

    duplicate_rate = calculate_percentage(
        duplicate_count,
        input_count
    )

    return {
        "run_id": pipeline_run.run_id,
        "status": pipeline_run.status,
        "input_count": input_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "duplicate_count": duplicate_count,
        "anomalous_session_count": anomalous_session_count or 0,
        "processing_duration_seconds": processing_duration_seconds,
        "acceptance_rate": acceptance_rate,
        "rejection_rate": rejection_rate,
        "duplicate_rate": duplicate_rate
    }
