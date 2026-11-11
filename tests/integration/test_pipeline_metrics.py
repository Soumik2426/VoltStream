from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.database import SessionLocal
from src.models import (
    Station,
    PipelineRun,
    ChargingSession
)
from src.monitoring.metrics import calculate_run_metrics


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def create_test_setup(db_session):
    unique_id = uuid4().hex[:8].upper()

    station_id = f"ST_{unique_id}"
    run_id = f"RUN_{unique_id}"

    station = Station(
        station_id=station_id,
        station_name="Metrics Test Station",
        city="Kolkata",
        max_power_kw=Decimal("50.00")
    )

    pipeline_run = PipelineRun(
        run_id=run_id,
        started_at=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 11, 10, 10, 0, 5, tzinfo=timezone.utc),
        input_count=100,
        accepted_count=80,
        rejected_count=10,
        duplicate_count=10,
        status="SUCCESS"
    )

    db_session.add_all([station, pipeline_run])
    db_session.flush()

    return station_id, run_id, unique_id


def test_calculate_run_metrics(db_session):
    station_id, run_id, unique_id = create_test_setup(db_session)

    try:
        result = calculate_run_metrics(db_session, run_id)

        assert result["run_id"] == run_id
        assert result["status"] == "SUCCESS"

        assert result["input_count"] == 100
        assert result["accepted_count"] == 80
        assert result["rejected_count"] == 10
        assert result["duplicate_count"] == 10

        assert result["acceptance_rate"] == 80.0
        assert result["rejection_rate"] == 10.0
        assert result["duplicate_rate"] == 10.0

        assert result["processing_duration_seconds"] == 5.0
        assert result["anomalous_session_count"] == 0

    finally:
        db_session.rollback()

        db_session.query(ChargingSession).filter_by(
            last_processed_run_id=run_id
        ).delete(synchronize_session=False)

        db_session.query(PipelineRun).filter_by(
            run_id=run_id
        ).delete(synchronize_session=False)

        db_session.query(Station).filter_by(
            station_id=station_id
        ).delete(synchronize_session=False)

        db_session.commit()


def test_calculate_anomalous_session_count(db_session):
    station_id, run_id, unique_id = create_test_setup(db_session)

    session_ids = [
        f"ANOMALOUS_{unique_id}_1",
        f"ANOMALOUS_{unique_id}_2"
    ]

    try:
        sessions = [
            ChargingSession(
                session_id=session_ids[0],
                station_id=station_id,
                session_status="ANOMALOUS",
                anomaly_reasons=["DECREASING_METER_READING"],
                last_processed_run_id=run_id
            ),
            ChargingSession(
                session_id=session_ids[1],
                station_id=station_id,
                session_status="ANOMALOUS",
                anomaly_reasons=["STOP_WITHOUT_START"],
                last_processed_run_id=run_id
            )
        ]

        db_session.add_all(sessions)
        db_session.flush()

        result = calculate_run_metrics(db_session, run_id)

        assert result["anomalous_session_count"] == 2

    finally:
        db_session.rollback()

        db_session.query(ChargingSession).filter(
            ChargingSession.session_id.in_(session_ids)
        ).delete(synchronize_session=False)

        db_session.query(PipelineRun).filter_by(
            run_id=run_id
        ).delete(synchronize_session=False)

        db_session.query(Station).filter_by(
            station_id=station_id
        ).delete(synchronize_session=False)

        db_session.commit()


def test_calculate_metrics_for_zero_input_records(db_session):
    station_id, run_id, unique_id = create_test_setup(db_session)

    try:
        pipeline_run = db_session.get(PipelineRun, run_id)

        pipeline_run.input_count = 0
        pipeline_run.accepted_count = 0
        pipeline_run.rejected_count = 0
        pipeline_run.duplicate_count = 0

        result = calculate_run_metrics(db_session, run_id)

        assert result["acceptance_rate"] == 0.0
        assert result["rejection_rate"] == 0.0
        assert result["duplicate_rate"] == 0.0

    finally:
        db_session.rollback()

        db_session.query(PipelineRun).filter_by(
            run_id=run_id
        ).delete(synchronize_session=False)

        db_session.query(Station).filter_by(
            station_id=station_id
        ).delete(synchronize_session=False)

        db_session.commit()


def test_calculate_metrics_for_nonexistent_run(db_session):
    nonexistent_run_id = f"NONEXISTENT_{uuid4().hex[:8]}"

    with pytest.raises(
        ValueError,
        match="does not exist"
    ):
        calculate_run_metrics(
            db_session,
            nonexistent_run_id
        )


def test_processing_duration_is_none_for_running_pipeline(db_session):
    unique_id = uuid4().hex[:8].upper()

    run_id = f"RUN_{unique_id}"

    pipeline_run = PipelineRun(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        completed_at=None,
        input_count=0,
        accepted_count=0,
        rejected_count=0,
        duplicate_count=0,
        status="RUNNING"
    )

    db_session.add(pipeline_run)
    db_session.flush()

    try:
        result = calculate_run_metrics(db_session, run_id)

        assert result["status"] == "RUNNING"
        assert result["processing_duration_seconds"] is None

    finally:
        db_session.rollback()

        db_session.query(PipelineRun).filter_by(
            run_id=run_id
        ).delete(synchronize_session=False)

        db_session.commit()
