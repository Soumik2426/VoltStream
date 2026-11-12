from uuid import uuid4

from sqlalchemy.orm import Session

from src.models.charging_event import ChargingEvent
from src.models.rejected_record import RejectedRecord


def store_charging_event(
    db_session: Session,
    event_data: dict
) -> ChargingEvent:

    event = ChargingEvent(
        event_id=event_data["event_id"],
        session_id=event_data["session_id"],
        station_id=event_data["station_id"],
        event_type=event_data["event_type"],
        event_timestamp=event_data["event_timestamp"],
        meter_kwh=event_data["meter_kwh"],
        source_file=event_data["source_file"],
        source_row_number=event_data["source_row_number"],
        run_id=event_data["run_id"]
    )

    db_session.add(event)

    return event


def store_rejected_record(
    db_session: Session,
    source_record: dict,
    source_file: str,
    source_row_number: int,
    run_id: str,
    errors: list[dict]
) -> list[RejectedRecord]:

    rejected_records = []

    for error in errors:

        rejected_record = RejectedRecord(
            reject_id=f"REJ_{uuid4().hex}",
            source_record=source_record,
            source_file=source_file,
            source_row_number=source_row_number,
            reason_code=error["reason_code"],
            reason_detail=error.get(
                "reason_detail",
                error["reason_code"]
            ),
            run_id=run_id
        )

        db_session.add(rejected_record)
        rejected_records.append(rejected_record)

    return rejected_records
