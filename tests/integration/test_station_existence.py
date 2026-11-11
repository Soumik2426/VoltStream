from decimal import Decimal
from uuid import uuid4

import pytest

from src.database import SessionLocal
from src.models import Station
from src.pipeline_processor import is_station_registered


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_existing_station_returns_true(db_session):
    station_id = f"TEST_ST_{uuid4().hex[:12]}"

    station = Station(
        station_id=station_id,
        station_name="Integration Test Station",
        city="Kolkata",
        max_power_kw=Decimal("50.00")
    )

    db_session.add(station)
    db_session.flush()

    assert is_station_registered(db_session, station_id) is True


def test_non_existing_station_returns_false(db_session):
    station_id = f"MISSING_{uuid4().hex[:12]}"

    assert is_station_registered(db_session, station_id) is False
