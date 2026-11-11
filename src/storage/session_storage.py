
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.charging_event import ChargingEvent
from src.models.charging_session import ChargingSession
from src.transformation.session_reconstructor import reconstruct_session


def rebuild_charging_session(
    db_session: Session,
    session_id: str,
    run_id: str
) -> ChargingSession:
    """
    Reconstruct a charging session using all its stored events
    and insert or update the corresponding database record.
    """

    # 1. Fetch all events belonging to this session.
    events = db_session.scalars(
        select(ChargingEvent)
        .where(ChargingEvent.session_id == session_id)
        .order_by(
            ChargingEvent.event_timestamp,
            ChargingEvent.event_id
        )
    ).all()

    if not events:
        raise ValueError(
            f"No charging events found for session {session_id}"
        )

    # 2. Reconstruct the session from its events.
    reconstructed = reconstruct_session(events)

    # 3. Use the station ID from the earliest event.
    station_id = events[0].station_id

    # 4. Check whether this session already exists.
    charging_session = db_session.get(
        ChargingSession,
        session_id
    )

    # 5. Prepare the reconstructed database fields.
    session_data = {
        "station_id": station_id,
        "start_time": reconstructed["start_time"],
        "end_time": reconstructed["end_time"],
        "start_meter_kwh": reconstructed["start_meter_kwh"],
        "end_meter_kwh": reconstructed["end_meter_kwh"],
        "energy_consumed_kwh": reconstructed["energy_consumed_kwh"],
        "duration_seconds": reconstructed["duration_seconds"],
        "session_status": reconstructed["session_status"],
        "anomaly_reasons": reconstructed["anomaly_reasons"],
        "last_processed_run_id": run_id,
    }

    # 6. Insert a new session or update the existing one.
    if charging_session is None:
        charging_session = ChargingSession(
            session_id=session_id,
            **session_data
        )
        db_session.add(charging_session)
    else:
        for field, value in session_data.items():
            setattr(charging_session, field, value)

    # The caller is responsible for committing the transaction.
    db_session.flush()

    return charging_session
