from datetime import datetime
from decimal import Decimal


def transform_charging_event(record: dict) -> dict:

    timestamp = datetime.fromisoformat(
        record["event_timestamp"]
    )

    meter_reading = Decimal(
        record["meter_kwh"]
    )

    return {
        "event_id": record["event_id"].strip(),
        "session_id": record["session_id"].strip(),
        "station_id": record["station_id"].strip(),
        "event_type": record["event_type"].strip().upper(),
        "event_timestamp": timestamp,
        "meter_kwh": meter_reading,
        "source_file": record["_source_file"],
        "source_row_number": record["_source_row_number"]
    }
