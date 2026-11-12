from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.database import SessionLocal
from src.models import (
    Station,
    PipelineRun,
    ChargingEvent,
    ChargingSession,
)
from src.storage.session_storage import rebuild_charging_session


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
        station_name="Session Storage Test Station",
        city="Kolkata",
        max_power_kw=Decimal("50.00")
    )

    pipeline_run = PipelineRun(
        run_id=run_id,
        started_at=datetime.now(timezone.utc),
        status="RUNNING"
    )

    db_session.add_all([station, pipeline_run])
    db_session.flush()

    return station_id, run_id, unique_id


def create_test_event(
    event_id,
    session_id,
    station_id,
    run_id,
    event_type,
    timestamp,
    meter_kwh
):
    return ChargingEvent(
        event_id=event_id,
        session_id=session_id,
        station_id=station_id,
        run_id=run_id,
        event_type=event_type,
        event_timestamp=timestamp,
        meter_kwh=Decimal(str(meter_kwh)),
        source_file="session_storage_test.csv",
        source_row_number=2
    )


def test_create_completed_charging_session(db_session):
    station_id, run_id, unique_id = create_test_setup(db_session)

    session_id = f"SESSION_{unique_id}"
    start_time = datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)

    events = [
        create_test_event(
            f"START_{unique_id}", session_id, station_id, run_id,
            "START", start_time, "100.000"
        ),
        create_test_event(
            f"STOP_{unique_id}", session_id, station_id, run_id,
            "STOP", start_time + timedelta(minutes=45), "125.000"
        )
    ]

    db_session.add_all(events)
    db_session.flush()

    result = rebuild_charging_session(
        db_session,
        session_id,
        run_id
    )

    assert result.session_id == session_id
    assert result.station_id == station_id
    assert result.session_status == "COMPLETED"
    assert result.energy_consumed_kwh == Decimal("25.000")
    assert result.duration_seconds == 2700
    assert result.last_processed_run_id == run_id
    assert result.anomaly_reasons == []


def test_update_existing_session_when_stop_event_arrives(db_session):
    station_id, run_id, unique_id = create_test_setup(db_session)

    session_id = f"UPDATE_SESSION_{unique_id}"
    start_time = datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)

    start_event = create_test_event(
        f"UPDATE_START_{unique_id}", session_id, station_id, run_id,
        "START", start_time, "100.000"
    )

    db_session.add(start_event)
    db_session.flush()

    # First reconstruction: only START exists.
    first_result = rebuild_charging_session(
        db_session,
        session_id,
        run_id
    )

    assert first_result.session_status == "IN_PROGRESS"
    assert first_result.end_time is None
    assert first_result.anomaly_reasons == []

    # A STOP event arrives later.
    stop_event = create_test_event(
        f"UPDATE_STOP_{unique_id}", session_id, station_id, run_id,
        "STOP", start_time + timedelta(minutes=30), "120.000"
    )

    db_session.add(stop_event)
    db_session.flush()

    # Reconstruct again using both stored events.
    second_result = rebuild_charging_session(
        db_session,
        session_id,
        run_id
    )

    assert second_result.session_status == "COMPLETED"
    assert second_result.energy_consumed_kwh == Decimal("20.000")
    assert second_result.duration_seconds == 1800
    assert second_result.anomaly_reasons == []

    # Verify that the existing row was updated, not duplicated.
    saved_session = db_session.get(ChargingSession, session_id)
    assert saved_session is not None
    assert saved_session.session_status == "COMPLETED"


def test_completed_session_without_intermediate_meter_reading(db_session):
    station_id, run_id, unique_id = create_test_setup(db_session)

    session_id = f"NO_METER_SESSION_{unique_id}"
    start_time = datetime(2026, 11, 10, 11, 0, tzinfo=timezone.utc)

    events = [
        create_test_event(
            f"NO_METER_START_{unique_id}", session_id, station_id, run_id,
            "START", start_time, "50.000"
        ),
        create_test_event(
            f"NO_METER_STOP_{unique_id}", session_id, station_id, run_id,
            "STOP", start_time + timedelta(minutes=20), "65.000"
        )
    ]

    db_session.add_all(events)
    db_session.flush()

    result = rebuild_charging_session(
        db_session,
        session_id,
        run_id
    )

    assert result.session_status == "COMPLETED"
    assert result.energy_consumed_kwh == Decimal("15.000")
    assert result.duration_seconds == 1200
    assert result.anomaly_reasons == []


def test_anomaly_reasons_are_persisted_in_database(db_session):
    station_id, run_id, unique_id = create_test_setup(db_session)

    session_id = f"ANOMALOUS_SESSION_{unique_id}"
    start_time = datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)

    events = [
        create_test_event(
            f"ANOMALY_START_{unique_id}", session_id, station_id, run_id,
            "START", start_time, "100.000"
        ),
        create_test_event(
            f"ANOMALY_METER_1_{unique_id}", session_id, station_id, run_id,
            "METER_READING", start_time + timedelta(minutes=15), "120.000"
        ),
        create_test_event(
            f"ANOMALY_METER_2_{unique_id}", session_id, station_id, run_id,
            "METER_READING", start_time + timedelta(minutes=30), "115.000"
        ),
        create_test_event(
            f"ANOMALY_STOP_{unique_id}", session_id, station_id, run_id,
            "STOP", start_time + timedelta(minutes=45), "140.000"
        )
    ]

    db_session.add_all(events)
    db_session.flush()

    result = rebuild_charging_session(
        db_session,
        session_id,
        run_id
    )

    assert result.session_status == "ANOMALOUS"

    assert result.anomaly_reasons == [
        "DECREASING_METER_READING"
    ]

    # Fetch the session again to verify that the reasons are persisted.
    db_session.flush()
    db_session.expire_all()

    saved_session = db_session.get(ChargingSession, session_id)

    assert saved_session is not None
    assert saved_session.session_status == "ANOMALOUS"
    assert saved_session.anomaly_reasons == [
        "DECREASING_METER_READING"
    ]
