
from decimal import Decimal

from src.database import SessionLocal
from src.models.station import Station


def seed_stations():
    stations = [
        Station(
            station_id="ST001",
            station_name="Salt Lake Charging Hub",
            city="Kolkata",
            max_power_kw=Decimal("120.00")
        ),
        Station(
            station_id="ST002",
            station_name="New Town Charging Hub",
            city="Kolkata",
            max_power_kw=Decimal("60.00")
        )
    ]

    with SessionLocal.begin() as session:
        for station in stations:
            existing_station = session.get(
                Station,
                station.station_id
            )

            if existing_station is None:
                session.add(station)
                print(f"Inserted station: {station.station_id}")
            else:
                print(f"Station already exists: {station.station_id}")


if __name__ == "__main__":
    seed_stations()
