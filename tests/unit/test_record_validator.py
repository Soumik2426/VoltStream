import pytest

from src.validation.record_validator import validate_record


def get_valid_record():
    return {
        "event_id": "EVT001",
        "session_id": "SES001",
        "station_id": "ST001",
        "event_type": "START",
        "event_timestamp": "2026-11-01T10:00:00Z",
        "meter_kwh": "0.000"
    }


def test_valid_record():
    record = get_valid_record()

    errors = validate_record(record)

    assert errors == []


def test_missing_event_id():
    record = get_valid_record()
    record["event_id"] = ""

    errors = validate_record(record)

    assert any(
        error["reason_code"] == "MISSING_REQUIRED_FIELD"
        for error in errors
    )


def test_invalid_event_type():
    record = get_valid_record()
    record["event_type"] = "CHARGE"

    errors = validate_record(record)

    assert any(
        error["reason_code"] == "INVALID_EVENT_TYPE"
        for error in errors
    )


def test_invalid_timestamp():
    record = get_valid_record()
    record["event_timestamp"] = "not-a-date"

    errors = validate_record(record)

    assert any(
        error["reason_code"] == "INVALID_TIMESTAMP"
        for error in errors
    )


def test_timestamp_without_timezone():
    record = get_valid_record()
    record["event_timestamp"] = "2026-11-01T10:00:00"

    errors = validate_record(record)

    assert any(
        error["reason_code"] == "TIMEZONE_MISSING"
        for error in errors
    )


def test_negative_meter_reading():
    record = get_valid_record()
    record["meter_kwh"] = "-5.5"

    errors = validate_record(record)

    assert any(
        error["reason_code"] == "NEGATIVE_METER_READING"
        for error in errors
    )


@pytest.mark.parametrize("meter_value", ["abc", "NaN", "Infinity"])
def test_invalid_meter_reading(meter_value):
    record = get_valid_record()
    record["meter_kwh"] = meter_value

    errors = validate_record(record)

    assert any(
        error["reason_code"] == "INVALID_METER_READING"
        for error in errors
    )


def test_empty_meter_reading():
    record = get_valid_record()
    record["meter_kwh"] = ""

    errors = validate_record(record)

    assert any(
        error["reason_code"] == "MISSING_REQUIRED_FIELD"
        for error in errors
    )


def test_extra_csv_columns():
    record = get_valid_record()
    record["_ingestion_error"] = "EXTRA_COLUMNS"

    errors = validate_record(record)

    assert any(
        error["reason_code"] == "EXTRA_COLUMNS"
        for error in errors
    )


def test_multiple_validation_errors():
    record = get_valid_record()
    record["event_type"] = "UNKNOWN"
    record["meter_kwh"] = "-10"

    errors = validate_record(record)

    reason_codes = {
        error["reason_code"]
        for error in errors
    }

    assert "INVALID_EVENT_TYPE" in reason_codes
    assert "NEGATIVE_METER_READING" in reason_codes
