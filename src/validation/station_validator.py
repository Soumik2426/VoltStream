from sqlalchemy.orm import Session

from src.models.station import Station


def validate_station_id(station_id: str, session: Session) -> list[dict]:
    """
    Check whether a station ID exists in PostgreSQL.

    Returns an empty list if the station exists.
    Otherwise, returns a list containing the validation error.
    """

    station = session.get(Station, station_id)

    if station is None:
        return [
            {
                "reason_code": "UNKNOWN_STATION",
                "reason_detail": f"Station '{station_id}' does not exist."
            }
        ]

    return []
