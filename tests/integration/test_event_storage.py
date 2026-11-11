from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from src.models import BatchFile
from src.pipeline import find_previously_processed_file
from sqlalchemy.exc import IntegrityError


import pytest

from src.database import SessionLocal
from src.models import Station, PipelineRun, ChargingEvent, RejectedRecord
from src.storage.event_storage import (
    store_charging_event,
    store_rejected_record
)


@pytest.fixture
def db_session():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def test_context(db_session):
    unique_id = uuid4().hex[:12].upper()

    station = Station(
        station_id=f"TST_{unique_id}",
        station_name="Test Station",
        city="Kolkata",
        max_power_kw=Decimal("50.00")
    )

    run = PipelineRun(
        run_id=f"TEST_RUN_{unique_id}",
        started_at=datetime.now(timezone.utc),
        status="RUNNING"
    )

    db_session.add_all([station, run])
    db_session.flush()

    yield {
        "station_id": station.station_id,
        "run_id": run.run_id,
        "unique_id": unique_id
    }


def test_store_charging_event(db_session, test_context):
    event_data = {
        "event_id": f"TEST_EVT_{test_context['unique_id']}",
        "session_id": f"TEST_SES_{test_context['unique_id']}",
        "station_id": test_context["station_id"],
        "event_type": "START",
        "event_timestamp": datetime.now(timezone.utc),
        "meter_kwh": Decimal("0.000"),
        "source_file": "test_events.csv",
        "source_row_number": 2,
        "run_id": test_context["run_id"]
    }

    event = store_charging_event(db_session, event_data)

    assert event.event_id == event_data["event_id"]

    db_session.flush()

    saved_event = db_session.get(ChargingEvent, event.event_id)

    assert saved_event is not None
    assert saved_event.station_id == event_data["station_id"]


def test_store_rejected_record(db_session, test_context):
    source_record = {
        "event_id": "BAD_EVT_001",
        "event_type": "UNKNOWN",
        "meter_kwh": "-10"
    }

    errors = [
        {
            "reason_code": "INVALID_EVENT_TYPE",
            "reason_detail": "Unsupported event type"
        },
        {
            "reason_code": "NEGATIVE_METER_READING",
            "reason_detail": "Meter reading cannot be negative"
        }
    ]

    rejected = store_rejected_record(
        db_session=db_session,
        source_record=source_record,
        source_file="test_events.csv",
        source_row_number=5,
        run_id=test_context["run_id"],
        errors=errors
    )

    assert len(rejected) == 2

    db_session.flush()

    saved_records = (
        db_session.query(RejectedRecord)
        .filter_by(run_id=test_context["run_id"])
        .all()
    )

    assert len(saved_records) == 2

    reason_codes = {record.reason_code for record in saved_records}

    assert reason_codes == {
        "INVALID_EVENT_TYPE",
        "NEGATIVE_METER_READING"
    }


def test_database_rejects_duplicate_event_id(db_session, test_context):
    event_data = {
        "event_id": f"DUP_EVT_{test_context['unique_id']}",
        "session_id": f"DUP_SES_{test_context['unique_id']}",
        "station_id": test_context["station_id"],
        "event_type": "START",
        "event_timestamp": datetime.now(timezone.utc),
        "meter_kwh": Decimal("0.000"),
        "source_file": "test_events.csv",
        "source_row_number": 2,
        "run_id": test_context["run_id"]
    }

    # First insertion should succeed.
    store_charging_event(db_session, event_data)
    db_session.flush()

    # Second insertion with the same primary key should fail.
    duplicate_event = dict(event_data)

    db_session.add(ChargingEvent(**duplicate_event))

    with pytest.raises(IntegrityError):
        db_session.flush()

    # Recover the SQLAlchemy session after the failed transaction.
    db_session.rollback()


def test_find_previously_processed_file(db_session, test_context):
    batch = BatchFile(
        batch_file_id=f"BATCH_{test_context['unique_id']}",
        run_id=test_context["run_id"],
        source_file="events.csv",
        file_checksum="test_checksum_123",
        file_status="SUCCESS",
        input_count=10,
        accepted_count=8,
        rejected_count=2,
        duplicate_count=0,
        started_at=datetime.now(timezone.utc)
    )

    db_session.add(batch)
    db_session.flush()

    result = find_previously_processed_file(
        db_session,
        "test_checksum_123"
    )

    assert result is not None
    assert result.batch_file_id == batch.batch_file_id


def test_unprocessed_file_returns_none(db_session):
    result = find_previously_processed_file(
        db_session,
        "checksum_that_does_not_exist"
    )

    assert result is None
