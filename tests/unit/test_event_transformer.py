from datetime import datetime
from decimal import Decimal

from src.transformation.event_transformer import (
    transform_charging_event
)


def test_transform_valid_charging_event():
    record = {
        "event_id": " EVT001 ",
        "session_id": " SESSION001 ",
        "station_id": " ST001 ",
        "event_type": "start",
        "event_timestamp": "2026-11-10T10:30:00+05:30",
        "meter_kwh": "125.500",
        "_source_file": "events.csv",
        "_source_row_number": 2
    }

    result = transform_charging_event(record)

    assert result["event_id"] == "EVT001"
    assert result["session_id"] == "SESSION001"
    assert result["station_id"] == "ST001"
    assert result["event_type"] == "START"

    assert isinstance(result["event_timestamp"], datetime)
    assert isinstance(result["meter_kwh"], Decimal)

    assert result["meter_kwh"] == Decimal("125.500")
    assert result["source_file"] == "events.csv"
    assert result["source_row_number"] == 2
