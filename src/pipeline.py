import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.models import PipelineRun, BatchFile, Station
from src.pipeline_processor import process_record
from src.ingestion.csv_reader import read_csv_file
from src.storage.event_storage import (
    store_charging_event,
    store_rejected_record
)
from src.storage.session_storage import rebuild_charging_session
from src.monitoring.logger import get_logger


logger = get_logger(__name__)


def create_pipeline_run(
    db_session: Session,
    source_file: str
) -> tuple[PipelineRun, BatchFile]:
    """
    Create tracking records for a new pipeline execution
    and the CSV file being processed.
    """

    run_id = f"RUN_{uuid4().hex}"

    pipeline_run = PipelineRun(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        status="RUNNING",
        input_count=0,
        accepted_count=0,
        rejected_count=0,
        duplicate_count=0
    )

    batch_file = BatchFile(
        batch_file_id=f"BATCH_{uuid4().hex}",
        run_id=run_id,
        source_file=source_file,
        file_checksum="PENDING",
        file_status="PROCESSING",
        input_count=0,
        accepted_count=0,
        rejected_count=0,
        duplicate_count=0,
        started_at=datetime.now(timezone.utc)
    )

    db_session.add(pipeline_run)
    db_session.add(batch_file)

    db_session.flush()

    logger.info(
        "Pipeline tracking records created | run_id=%s | file=%s",
        run_id,
        source_file
    )

    return pipeline_run, batch_file


def calculate_file_checksum(file_path: str) -> str:

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def find_previously_processed_file(
    db_session: Session,
    checksum: str
) -> BatchFile | None:

    existing_file = (
        db_session.query(BatchFile)
        .filter(
            BatchFile.file_checksum == checksum,
            BatchFile.file_status.in_([
                "PROCESSING",
                "SUCCESS",
                "PARTIAL_SUCCESS"
            ])
        )
        .first()
    )

    return existing_file


def register_batch_file(
    db_session: Session,
    file_path: str
) -> tuple[PipelineRun | None, BatchFile, bool]:

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Input file not found: {file_path}"
        )

    checksum = calculate_file_checksum(str(path))

    existing_file = find_previously_processed_file(
        db_session,
        checksum
    )

    if existing_file is not None:
        logger.warning(
            "Duplicate file detected | existing_batch_id=%s | file=%s",
            existing_file.batch_file_id,
            path.name
        )

        return None, existing_file, True

    pipeline_run, batch_file = create_pipeline_run(
        db_session,
        path.name
    )

    batch_file.file_checksum = checksum

    db_session.flush()

    return pipeline_run, batch_file, False


def process_csv_file(
    db_session: Session,
    file_path: str
) -> dict:
    """
    Process a CSV file and track successful or failed execution.
    """

    pipeline_run = None
    batch_file = None

    try:
        # Step 1: Register the file.
        pipeline_run, batch_file, is_duplicate = register_batch_file(
            db_session,
            file_path
        )

        if is_duplicate:
            return {
                "status": "DUPLICATE_FILE",
                "batch_file_id": batch_file.batch_file_id
            }

        run_id = pipeline_run.run_id
        start_time = pipeline_run.started_at

        logger.info(
            "Pipeline started | run_id=%s | file=%s",
            run_id,
            file_path
        )

        input_count = 0
        accepted_count = 0
        rejected_count = 0
        duplicate_count = 0

        affected_session_ids = set()

        logger.info(
            "CSV processing started | run_id=%s",
            run_id
        )

        # Step 2: Process CSV records.
        for record in read_csv_file(file_path):

            input_count += 1

            result = process_record(record, db_session)

            if result["status"] == "ACCEPTED":

                event_data = {
                    **result["event"],
                    "run_id": run_id
                }

                store_charging_event(db_session, event_data)
                db_session.flush()

                affected_session_ids.add(
                    event_data["session_id"]
                )

                accepted_count += 1

            elif result["status"] == "REJECTED":

                store_rejected_record(
                    db_session=db_session,
                    source_record=record,
                    source_file=record["_source_file"],
                    source_row_number=record["_source_row_number"],
                    run_id=run_id,
                    errors=result["errors"]
                )

                rejected_count += 1

            elif result["status"] == "DUPLICATE":

                duplicate_count += 1

        # Step 3: Reconstruct affected charging sessions.
        logger.info(
            "Reconstructing charging sessions | run_id=%s | session_count=%s",
            run_id,
            len(affected_session_ids)
        )

        for session_id in sorted(affected_session_ids):

            rebuild_charging_session(
                db_session=db_session,
                session_id=session_id,
                run_id=run_id
            )

        # Step 4: Determine final file status.
        if rejected_count > 0 or duplicate_count > 0:
            final_file_status = "PARTIAL_SUCCESS"
        else:
            final_file_status = "SUCCESS"

        # Step 5: Update pipeline metrics.
        pipeline_run.input_count = input_count
        pipeline_run.accepted_count = accepted_count
        pipeline_run.rejected_count = rejected_count
        pipeline_run.duplicate_count = duplicate_count
        pipeline_run.status = "SUCCESS"
        pipeline_run.completed_at = datetime.now(timezone.utc)

        # Step 6: Update batch metrics.
        batch_file.input_count = input_count
        batch_file.accepted_count = accepted_count
        batch_file.rejected_count = rejected_count
        batch_file.duplicate_count = duplicate_count
        batch_file.file_status = final_file_status
        batch_file.completed_at = datetime.now(timezone.utc)

        # Calculate processing duration.
        duration = round(
            (pipeline_run.completed_at - start_time).total_seconds(),
            3
        )

        # Step 7: Commit successful processing.
        db_session.commit()

        logger.info(
            "Records processed | run_id=%s | input=%s | accepted=%s | rejected=%s | duplicates=%s",
            run_id,
            input_count,
            accepted_count,
            rejected_count,
            duplicate_count
        )

        logger.info(
            "Pipeline completed | run_id=%s | status=%s | duration_seconds=%s",
            run_id,
            final_file_status,
            duration
        )

        return {
            "run_id": run_id,
            "batch_file_id": batch_file.batch_file_id,
            "status": final_file_status,
            "input_count": input_count,
            "accepted_count": accepted_count,
            "rejected_count": rejected_count,
            "duplicate_count": duplicate_count
        }

    except Exception as error:

        # Capture tracking information before rollback.
        run_id = pipeline_run.run_id if pipeline_run else None

        source_file = (
            batch_file.source_file
            if batch_file
            else Path(file_path).name
        )

        checksum = (
            batch_file.file_checksum
            if batch_file
            else None
        )

        batch_id = (
            batch_file.batch_file_id
            if batch_file
            else None
        )

        logger.exception(
            "Pipeline processing failed | run_id=%s | file=%s",
            run_id or "NOT_CREATED",
            source_file
        )

        # Roll back all uncommitted processing operations.
        db_session.rollback()

        if run_id is not None:

            # Recreate failed-run tracking in a new transaction.
            try:
                failed_at = datetime.now(timezone.utc)

                failed_run = PipelineRun(
                    run_id=run_id,
                    started_at=failed_at,
                    completed_at=failed_at,
                    input_count=0,
                    accepted_count=0,
                    rejected_count=0,
                    duplicate_count=0,
                    status="FAILED",
                    error_message=str(error)[:1000]
                )

                db_session.add(failed_run)
                db_session.flush()

                failed_batch = BatchFile(
                    batch_file_id=batch_id,
                    run_id=run_id,
                    source_file=source_file,
                    file_checksum=checksum or "UNKNOWN",
                    file_status="FAILED",
                    input_count=0,
                    accepted_count=0,
                    rejected_count=0,
                    duplicate_count=0,
                    started_at=failed_at,
                    completed_at=failed_at,
                    error_message=str(error)[:1000]
                )

                db_session.add(failed_batch)
                db_session.commit()

                logger.error(
                    "Failed pipeline execution tracked | run_id=%s",
                    run_id
                )

            except Exception:
                db_session.rollback()
                logger.exception(
                    "Could not persist failed pipeline tracking | run_id=%s",
                    run_id
                )
                raise

        raise
