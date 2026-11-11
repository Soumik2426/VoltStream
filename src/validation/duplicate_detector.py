from sqlalchemy.orm import Session

from src.models.charging_event import ChargingEvent


def is_duplicate_event(event_id: str, session: Session) -> bool:
    """
    Check whether an event ID already exists
    in the charging_events table.
    """

    existing_event = session.get(ChargingEvent, event_id)

    return existing_event is not None
