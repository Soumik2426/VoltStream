
from datetime import datetime, timezone
import src.pipeline as pipeline_module
import csv
from decimal import Decimal
from uuid import uuid4

import pytest

from src.database import SessionLocal
from src.models import (
    Station,
    PipelineRun,
    BatchFile,
    ChargingEvent,
    RejectedRecord,
    ChargingSession
)
from src.pipeline import process_csv_file


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_process_csv_file(db_session, tmp_path):
    unique_id = uuid4().hex[:12].upper()

    station_id = f"TEST_ST_{unique_id}"
    session_id = f"SES_{unique_id}"
    event_id = f"TEST_EVT_{unique_id}"

    # Create a station required by the charging events.
    station = Station(
        station_id=station_id,
        station_name="Pipeline Integration Station",
        city="Kolkata",
        max_power_kw=Decimal("50.00")
    )

    db_session.add(station)
    db_session.flush()

    # Create a CSV containing valid, duplicate and invalid records.
    file_path = tmp_path / "pipeline_test.csv"

    fieldnames = [
        "event_id",
        "session_id",
        "station_id",
        "event_type",
        "event_timestamp",
        "meter_kwh"
    ]

    records = [
        {
            "event_id": event_id,
            "session_id": session_id,
            "station_id": station_id,
            "event_type": "START",
            "event_timestamp": "2026-11-10T10:30:00+05:30",
            "meter_kwh": "0.000"
        },
        {
            "event_id": event_id,
            "session_id": session_id,
            "station_id": station_id,
            "event_type": "START",
            "event_timestamp": "2026-11-10T10:30:00+05:30",
            "meter_kwh": "0.000"
        },
        {
            "event_id": f"BAD_EVT_{unique_id}",
            "session_id": session_id,
            "station_id": station_id,
            "event_type": "UNKNOWN",
            "event_timestamp": "2026-11-10T10:35:00+05:30",
            "meter_kwh": "-10"
        }
    ]

    with file_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    run_id = None

    try:
        # Execute the actual pipeline.
        result = process_csv_file(
            db_session,
            str(file_path)
        )

        run_id = result["run_id"]

        # Verify pipeline metrics.
        assert result["status"] == "PARTIAL_SUCCESS"
        assert result["input_count"] == 3
        assert result["accepted_count"] == 1
        assert result["rejected_count"] == 1
        assert result["duplicate_count"] == 1

        # Verify the accepted event was stored.
        saved_event = db_session.get(
            ChargingEvent,
            event_id
        )

        assert saved_event is not None
        assert saved_event.run_id == run_id

        # Verify the charging session was reconstructed.
        saved_session = db_session.get(
            ChargingSession,
            session_id
        )

        assert saved_session is not None
        assert saved_session.session_status == "IN_PROGRESS"
        assert saved_session.last_processed_run_id == run_id

        # Verify the rejected record was stored.
        rejected_records = (
            db_session.query(RejectedRecord)
            .filter_by(run_id=run_id)
            .all()
        )

        assert len(rejected_records) >= 1

        # Verify the batch-file tracking record.
        batch = (
            db_session.query(BatchFile)
            .filter_by(run_id=run_id)
            .one()
        )

        assert batch.file_status == "PARTIAL_SUCCESS"
        assert batch.input_count == 3
        assert batch.accepted_count == 1
        assert batch.rejected_count == 1
        assert batch.duplicate_count == 1

        # Verify the pipeline-run tracking record.
        pipeline_run = db_session.get(
            PipelineRun,
            run_id
        )

        assert pipeline_run.status == "SUCCESS"

    finally:
        # The pipeline commits its transaction.
        # Explicitly remove test data to keep the database clean.

        if run_id is not None:

            # Delete the reconstructed session first because it
            # references the pipeline run.
            db_session.query(ChargingSession).filter_by(
                session_id=session_id
            ).delete(synchronize_session=False)

            db_session.query(RejectedRecord).filter_by(
                run_id=run_id
            ).delete(synchronize_session=False)

            db_session.query(ChargingEvent).filter_by(
                run_id=run_id
            ).delete(synchronize_session=False)

            db_session.query(BatchFile).filter_by(
                run_id=run_id
            ).delete(synchronize_session=False)

            db_session.query(PipelineRun).filter_by(
                run_id=run_id
            ).delete(synchronize_session=False)

        db_session.query(Station).filter_by(
            station_id=station_id
        ).delete(synchronize_session=False)

        db_session.commit()


def test_pipeline_failure_rolls_back_and_tracks_failure(
    db_session,
    tmp_path,
    monkeypatch
):
    unique_id = uuid4().hex[:12].upper()

    station_id = f"FAIL_ST_{unique_id}"
    session_id = f"SES_{unique_id}"
    event_id = f"FAIL_EVT_{unique_id}"

    # Create a station for the valid event.
    station = Station(
        station_id=station_id,
        station_name="Failure Test Station",
        city="Kolkata",
        max_power_kw=Decimal("50.00")
    )

    db_session.add(station)
    db_session.flush()

    # Create a physical input file.
    file_path = tmp_path / "failure_test.csv"
    file_path.write_text(
        "event_id,event_type\nEVT001,START\n",
        encoding="utf-8"
    )

    # This record should be accepted and inserted first.
    valid_record = {
        "event_id": event_id,
        "session_id": session_id,
        "station_id": station_id,
        "event_type": "START",
        "event_timestamp": "2026-11-10T10:30:00+05:30",
        "meter_kwh": "0.000",
        "_source_file": file_path.name,
        "_source_row_number": 2
    }

    # Simulate an unexpected failure after yielding one record.
    def broken_reader(_file_path):
        yield valid_record
        raise RuntimeError("Simulated pipeline failure")

    monkeypatch.setattr(
        pipeline_module,
        "read_csv_file",
        broken_reader
    )

    try:
        with pytest.raises(
            RuntimeError,
            match="Simulated pipeline failure"
        ):
            process_csv_file(db_session, str(file_path))

        # Verify that the accepted event was rolled back.
        saved_event = db_session.get(
            ChargingEvent,
            event_id
        )

        assert saved_event is None

        # Verify that no reconstructed session was persisted.
        saved_session = db_session.get(
            ChargingSession,
            session_id
        )

        assert saved_session is None

        # Verify that failed-run tracking was recreated.
        failed_run = (
            db_session.query(PipelineRun)
            .filter(
                PipelineRun.error_message ==
                "Simulated pipeline failure"
            )
            .one()
        )

        assert failed_run.status == "FAILED"

        failed_batch = (
            db_session.query(BatchFile)
            .filter_by(run_id=failed_run.run_id)
            .one()
        )

        assert failed_batch.file_status == "FAILED"
        assert failed_batch.error_message == (
            "Simulated pipeline failure"
        )

    finally:
        # Clean up committed test data.
        failed_runs = (
            db_session.query(PipelineRun)
            .filter(
                PipelineRun.error_message ==
                "Simulated pipeline failure"
            )
            .all()
        )

        for run in failed_runs:

            db_session.query(ChargingSession).filter_by(
                last_processed_run_id=run.run_id
            ).delete(synchronize_session=False)

            db_session.query(ChargingEvent).filter_by(
                run_id=run.run_id
            ).delete(synchronize_session=False)

            db_session.query(RejectedRecord).filter_by(
                run_id=run.run_id
            ).delete(synchronize_session=False)

            db_session.query(BatchFile).filter_by(
                run_id=run.run_id
            ).delete(synchronize_session=False)

            db_session.delete(run)

        db_session.query(Station).filter_by(
            station_id=station_id
        ).delete(synchronize_session=False)

        db_session.commit()



def test_late_arriving_stop_event_updates_existing_session(
    db_session,
    tmp_path
):
    unique_id = uuid4().hex[:12].upper()

    station_id = f"LATE_{unique_id}"
    session_id = f"LATE_SES_{unique_id}"

    run_ids = []

    start_time = datetime(
        2026, 11, 10, 10, 0,
        tzinfo=timezone.utc
    )

    stop_time = datetime(
        2026, 11, 10, 10, 45,
        tzinfo=timezone.utc
    )

    station = Station(
        station_id=station_id,
        station_name="Late Event Test Station",
        city="Kolkata",
        max_power_kw=Decimal("50.00")
    )

    db_session.add(station)
    db_session.flush()

    fieldnames = [
        "event_id",
        "session_id",
        "station_id",
        "event_type",
        "event_timestamp",
        "meter_kwh"
    ]

    # First CSV: only the START event arrives.
    start_file = tmp_path / f"start_{unique_id}.csv"

    start_records = [
        {
            "event_id": f"LATE_START_{unique_id}",
            "session_id": session_id,
            "station_id": station_id,
            "event_type": "START",
            "event_timestamp": start_time.isoformat(),
            "meter_kwh": "100.000"
        }
    ]

    # Second CSV: the STOP event arrives later.
    stop_file = tmp_path / f"stop_{unique_id}.csv"

    stop_records = [
        {
            "event_id": f"LATE_STOP_{unique_id}",
            "session_id": session_id,
            "station_id": station_id,
            "event_type": "STOP",
            "event_timestamp": stop_time.isoformat(),
            "meter_kwh": "125.000"
        }
    ]

    def write_csv(file_path, records):
        with file_path.open(
            "w",
            newline="",
            encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames
            )
            writer.writeheader()
            writer.writerows(records)

    write_csv(start_file, start_records)
    write_csv(stop_file, stop_records)

    try:
        # Process the first CSV.
        first_result = process_csv_file(
            db_session,
            str(start_file)
        )

        run_ids.append(first_result["run_id"])

        assert first_result["status"] == "SUCCESS"
        assert first_result["accepted_count"] == 1

        # Verify that the session is initially IN_PROGRESS.
        first_session = db_session.get(
            ChargingSession,
            session_id
        )

        assert first_session is not None
        assert first_session.session_status == "IN_PROGRESS"
        assert first_session.end_time is None

        # Process the second CSV containing the late STOP event.
        second_result = process_csv_file(
            db_session,
            str(stop_file)
        )

        run_ids.append(second_result["run_id"])

        assert second_result["status"] == "SUCCESS"
        assert second_result["accepted_count"] == 1

        # Verify that the existing session was reconstructed.
        updated_session = db_session.get(
            ChargingSession,
            session_id
        )

        assert updated_session is not None
        assert updated_session.session_status == "COMPLETED"
        assert updated_session.start_time == start_time
        assert updated_session.end_time == stop_time
        assert updated_session.start_meter_kwh == Decimal("100.000")
        assert updated_session.end_meter_kwh == Decimal("125.000")
        assert updated_session.energy_consumed_kwh == Decimal("25.000")
        assert updated_session.duration_seconds == 2700

        # The session should reference the latest processing run.
        assert updated_session.last_processed_run_id == second_result["run_id"]

    finally:
        # Remove committed test data.
        db_session.rollback()

        db_session.query(ChargingSession).filter_by(
            session_id=session_id
        ).delete(synchronize_session=False)

        db_session.query(ChargingEvent).filter_by(
            session_id=session_id
        ).delete(synchronize_session=False)

        for run_id in run_ids:
            db_session.query(RejectedRecord).filter_by(
                run_id=run_id
            ).delete(synchronize_session=False)

            db_session.query(BatchFile).filter_by(
                run_id=run_id
            ).delete(synchronize_session=False)

            db_session.query(PipelineRun).filter_by(
                run_id=run_id
            ).delete(synchronize_session=False)

        db_session.query(Station).filter_by(
            station_id=station_id
        ).delete(synchronize_session=False)

        db_session.commit()


def test_late_arriving_meter_reading_before_stop_is_handled_correctly(
    db_session,
    tmp_path
):
    unique_id = uuid4().hex[:12].upper()

    station_id = f"LM_{unique_id}"
    session_id = f"LATE_METER_{unique_id}"

    run_ids = []

    start_time = datetime(
        2026, 11, 10, 10, 0,
        tzinfo=timezone.utc
    )

    meter_time = datetime(
        2026, 11, 10, 10, 20,
        tzinfo=timezone.utc
    )

    stop_time = datetime(
        2026, 11, 10, 10, 30,
        tzinfo=timezone.utc
    )

    station = Station(
        station_id=station_id,
        station_name="Late Meter Test Station",
        city="Kolkata",
        max_power_kw=Decimal("50.00")
    )

    db_session.add(station)
    db_session.flush()

    fieldnames = [
        "event_id",
        "session_id",
        "station_id",
        "event_type",
        "event_timestamp",
        "meter_kwh"
    ]

    # First CSV contains START and STOP.
    first_file = tmp_path / f"initial_events_{unique_id}.csv"

    first_records = [
        {
            "event_id": f"LM_START_{unique_id}",
            "session_id": session_id,
            "station_id": station_id,
            "event_type": "START",
            "event_timestamp": start_time.isoformat(),
            "meter_kwh": "100.000"
        },
        {
            "event_id": f"LM_STOP_{unique_id}",
            "session_id": session_id,
            "station_id": station_id,
            "event_type": "STOP",
            "event_timestamp": stop_time.isoformat(),
            "meter_kwh": "125.000"
        }
    ]

    # Second CSV contains a METER_READING that arrives late.
    # Its actual event timestamp is BEFORE the STOP event.
    second_file = tmp_path / f"late_meter_{unique_id}.csv"

    second_records = [
        {
            "event_id": f"LM_READING_{unique_id}",
            "session_id": session_id,
            "station_id": station_id,
            "event_type": "METER_READING",
            "event_timestamp": meter_time.isoformat(),
            "meter_kwh": "115.000"
        }
    ]

    def write_csv(file_path, records):
        with file_path.open(
            "w",
            newline="",
            encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames
            )
            writer.writeheader()
            writer.writerows(records)

    write_csv(first_file, first_records)
    write_csv(second_file, second_records)

    try:
        # Process the first CSV.
        first_result = process_csv_file(
            db_session,
            str(first_file)
        )

        run_ids.append(first_result["run_id"])

        assert first_result["status"] == "SUCCESS"
        assert first_result["accepted_count"] == 2

        # The session should already be COMPLETED.
        first_session = db_session.get(
            ChargingSession,
            session_id
        )

        assert first_session is not None
        assert first_session.session_status == "COMPLETED"
        assert first_session.energy_consumed_kwh == Decimal("25.000")
        assert first_session.anomaly_reasons == []

        # Process the second CSV containing the late meter reading.
        second_result = process_csv_file(
            db_session,
            str(second_file)
        )

        run_ids.append(second_result["run_id"])

        assert second_result["status"] == "SUCCESS"
        assert second_result["accepted_count"] == 1

        # Verify that all three events were used during reconstruction.
        db_session.expire_all()

        updated_session = db_session.get(
            ChargingSession,
            session_id
        )

        assert updated_session is not None
        assert updated_session.session_status == "COMPLETED"

        assert updated_session.start_time == start_time
        assert updated_session.end_time == stop_time

        assert updated_session.start_meter_kwh == Decimal("100.000")
        assert updated_session.end_meter_kwh == Decimal("125.000")

        assert updated_session.energy_consumed_kwh == Decimal("25.000")
        assert updated_session.duration_seconds == 1800

        # The late event must not create an anomaly.
        assert updated_session.anomaly_reasons == []

        # The session should reference the latest processing run.
        assert (
            updated_session.last_processed_run_id
            == second_result["run_id"]
        )

    finally:
        # Remove committed test data.
        db_session.rollback()

        db_session.query(ChargingSession).filter_by(
            session_id=session_id
        ).delete(synchronize_session=False)

        db_session.query(ChargingEvent).filter_by(
            session_id=session_id
        ).delete(synchronize_session=False)

        for run_id in run_ids:
            db_session.query(RejectedRecord).filter_by(
                run_id=run_id
            ).delete(synchronize_session=False)

            db_session.query(BatchFile).filter_by(
                run_id=run_id
            ).delete(synchronize_session=False)

            db_session.query(PipelineRun).filter_by(
                run_id=run_id
            ).delete(synchronize_session=False)

        db_session.query(Station).filter_by(
            station_id=station_id
        ).delete(synchronize_session=False)

        db_session.commit()

