from datetime import datetime
from decimal import Decimal, InvalidOperation


VALID_EVENT_TYPES = {
    "START",
    "METER_READING",
    "STOP"
}

REQUIRED_FIELDS = [
    "event_id",
    "session_id",
    "station_id",
    "event_type",
    "event_timestamp",
    "meter_kwh"
]


def validate_record(record: dict) -> list[dict]:

    errors = []

    # 1. Check for extra CSV columns.
    if record.get("_ingestion_error") == "EXTRA_COLUMNS":
        errors.append({
            "reason_code": "EXTRA_COLUMNS",
            "reason_detail": "Record contains more values than the CSV header."
        })

    # 2. Check required fields.
    for field in REQUIRED_FIELDS:
        value = record.get(field)

        if value is None or str(value).strip() == "":
            errors.append({
                "reason_code": "MISSING_REQUIRED_FIELD",
                "reason_detail": f"Required field '{field}' is missing."
            })

    # Do not perform further checks on missing values.
    if errors and any(
        error["reason_code"] == "MISSING_REQUIRED_FIELD"
        for error in errors
    ):
        return errors

    # 3. Validate event ID.
    if not isinstance(record["event_id"], str):
        errors.append({
            "reason_code": "INVALID_EVENT_ID",
            "reason_detail": "Event ID must be a string."
        })

    # 4. Validate event type.
    event_type = record["event_type"].strip().upper()

    if event_type not in VALID_EVENT_TYPES:
        errors.append({
            "reason_code": "INVALID_EVENT_TYPE",
            "reason_detail": f"Unsupported event type: {record['event_type']}"
        })

    # 5. Validate timestamp.
    try:
        timestamp = datetime.fromisoformat(
            record["event_timestamp"].strip().replace("Z", "+00:00")
        )

        if timestamp.tzinfo is None:
            errors.append({
                "reason_code": "TIMEZONE_MISSING",
                "reason_detail": "Event timestamp must include a timezone."
            })

    except (ValueError, AttributeError):
        errors.append({
            "reason_code": "INVALID_TIMESTAMP",
            "reason_detail": "Event timestamp is not a valid ISO 8601 timestamp."
        })

    # 6. Validate meter reading.
    try:
        meter_value = Decimal(record["meter_kwh"].strip())

        if not meter_value.is_finite():
            raise InvalidOperation

        if meter_value < 0:
            errors.append({
                "reason_code": "NEGATIVE_METER_READING",
                "reason_detail": "Meter reading cannot be negative."
            })

    except (InvalidOperation, ValueError, AttributeError):
        errors.append({
            "reason_code": "INVALID_METER_READING",
            "reason_detail": "Meter reading must be a valid finite number."
        })

    return errors
