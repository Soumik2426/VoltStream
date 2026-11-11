import pytest

from src.database import SessionLocal
from src.validation.station_validator import validate_station_id


@pytest.fixture
def db_session():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


def test_existing_station(db_session):
    errors = validate_station_id("ST001", db_session)

    assert errors == []


def test_unknown_station(db_session):
    errors = validate_station_id("ST999", db_session)

    assert len(errors) == 1
    assert errors[0]["reason_code"] == "UNKNOWN_STATION"
