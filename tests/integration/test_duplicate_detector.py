from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.database import SessionLocal
from src.models.pipeline_run import PipelineRun
from src.models.charging_event import ChargingEvent
from src.validation.duplicate_detector import is_duplicate_event


@pytest.fixture
def db_session():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def existing_event(db_session):
    unique_id = uuid4().hex[:12].upper()

    run = PipelineRun(
        run_id=f"TEST_RUN_{unique_id}",
        started_at=datetime.now(timezone.utc),
        status="RUNNING"
    )

    # Save the parent pipeline run first.
    db_session.add(run)
    db_session.flush()

    event = ChargingEvent(
        event_id=f"TEST_EVT_{unique_id}",
        session_id=f"TEST_SES_{unique_id}",
        station_id="ST001",
        event_type="START",
        event_timestamp=datetime.now(timezone.utc),
        meter_kwh=0,
        source_file="test_file.csv",
        source_row_number=2,
        run_id=run.run_id
    )

    # Now save the charging event.
    db_session.add(event)
    db_session.commit()

    yield event.event_id

    # Clean up in reverse foreign-key order.
    db_session.delete(event)
    db_session.delete(run)
    db_session.commit()


def test_existing_event_is_duplicate(db_session, existing_event):
    result = is_duplicate_event(existing_event, db_session)

    assert result is True


def test_non_existing_event_is_not_duplicate(db_session):
    result = is_duplicate_event("NON_EXISTENT_EVENT", db_session)

    assert result is False
