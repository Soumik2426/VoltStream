from src.validation.duplicate_detector import is_duplicate_event
from sqlalchemy.orm import Session
from src.models import Station
from src.validation.record_validator import validate_record
from src.transformation.event_transformer import transform_charging_event



def process_record(
    record: dict,
    db_session: Session
) -> dict:
    """
    Validate, verify station existence, detect duplicate events,
    and transform one charging-event record.
    """

    # Step 1: Validate record data.
    errors = validate_record(record)

    if errors:
        return {
            "status": "REJECTED",
            "event": None,
            "errors": errors
        }

    # Step 2: Verify station existence.
    station_id = record["station_id"].strip()

    if not is_station_registered(db_session, station_id):
        return {
            "status": "REJECTED",
            "event": None,
            "errors": [
                {
                    "reason_code": "UNKNOWN_STATION",
                    "reason_detail": f"Station {station_id} does not exist"
                }
            ]
        }

    # Step 3: Check event-level duplicates.
    event_id = record["event_id"].strip()

    if is_duplicate_event(event_id, db_session):
        return {
            "status": "DUPLICATE",
            "event": None,
            "errors": []
        }

    # Step 4: Transform the valid record.
    transformed_event = transform_charging_event(record)

    return {
        "status": "ACCEPTED",
        "event": transformed_event,
        "errors": []
    }




def is_station_registered(
    db_session: Session,
    station_id: str
) -> bool:
    """
    Check whether a charging station exists in the database.
    """

    station = db_session.get(Station, station_id)

    return station is not None

