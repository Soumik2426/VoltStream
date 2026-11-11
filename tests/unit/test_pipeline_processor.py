from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timezone
from src.models import PipelineRun, ChargingEvent
import pytest

from src.database import SessionLocal
from src.models import Station
from src.pipeline_processor import process_record


def create_test_run(db_session):
    run = PipelineRun(
        run_id=f"TEST_RUN_{uuid4().hex[:12]}",
        started_at=datetime.now(timezone.utc),
        status="RUNNING",
        input_count=0,
        accepted_count=0,
        rejected_count=0,
        duplicate_count=0
    )

    db_session.add(run)
    db_session.flush()

    return run.run_id


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def test_station(db_session):
    station_id = f"TEST_ST_{uuid4().hex[:12]}"

    station = Station(
        station_id=station_id,
        station_name="Test Station",
        city="Kolkata",
        max_power_kw=Decimal("50.00")
    )

    db_session.add(station)
    db_session.flush()

    return station_id


def test_process_valid_record(db_session, test_station):
    record = {
        "event_id": "EVT_TEST_001",
        "session_id": "SES_TEST_001",
        "station_id": test_station,
        "event_type": "START",
        "event_timestamp": "2026-11-10T10:30:00+05:30",
        "meter_kwh": "0.000",
        "_source_file": "events.csv",
        "_source_row_number": 2
    }

    result = process_record(record, db_session)

    assert result["status"] == "ACCEPTED"
    assert result["event"] is not None
    assert result["errors"] == []


def test_process_invalid_record(db_session, test_station):
    record = {
        "event_id": "",
        "session_id": "SES_TEST_001",
        "station_id": test_station,
        "event_type": "UNKNOWN",
        "event_timestamp": "invalid_timestamp",
        "meter_kwh": "-10",
        "_source_file": "events.csv",
        "_source_row_number": 3
    }

    result = process_record(record, db_session)

    assert result["status"] == "REJECTED"
    assert result["event"] is None
    assert len(result["errors"]) > 0


def test_process_record_with_unknown_station(db_session):
    record = {
        "event_id": f"EVT_{uuid4().hex[:12]}",
        "session_id": "SES_TEST_001",
        "station_id": "UNKNOWN_STATION",
        "event_type": "START",
        "event_timestamp": "2026-11-10T10:30:00+05:30",
        "meter_kwh": "0.000",
        "_source_file": "events.csv",
        "_source_row_number": 4
    }

    result = process_record(record, db_session)

    assert result["status"] == "REJECTED"
    assert result["event"] is None
    assert result["errors"][0]["reason_code"] == "UNKNOWN_STATION"



def test_process_duplicate_event(db_session, test_station):
    event_id = f"EVT_DUP_{uuid4().hex[:12]}"

    existing_event = ChargingEvent(
        event_id=event_id,
        session_id="SES_EXISTING",
        station_id=test_station,
        event_type="START",
        event_timestamp=datetime.now(timezone.utc),
        meter_kwh=Decimal("0.000"),
        source_file="previous.csv",
        source_row_number=2,
        run_id=create_test_run(db_session)
    )

    db_session.add(existing_event)
    db_session.flush()

    record = {
        "event_id": event_id,
        "session_id": "SES_NEW",
        "station_id": test_station,
        "event_type": "START",
        "event_timestamp": "2026-11-10T10:30:00+05:30",
        "meter_kwh": "0.000",
        "_source_file": "new.csv",
        "_source_row_number": 2
    }

    result = process_record(record, db_session)

    assert result["status"] == "DUPLICATE"
    assert result["event"] is None

