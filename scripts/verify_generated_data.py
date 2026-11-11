import csv
from collections import Counter
from pathlib import Path

CSV_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "generated"
    / "charging_events_generated.csv"
)

EXPECTED_COLUMNS = [
    "event_id",
    "session_id",
    "station_id",
    "event_type",
    "event_timestamp",
    "meter_kwh",
]


def main():
    if not CSV_FILE.exists():
        raise FileNotFoundError(f"Generated CSV not found: {CSV_FILE}")

    with CSV_FILE.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if reader.fieldnames != EXPECTED_COLUMNS:
            raise ValueError(
                f"Unexpected CSV columns: {reader.fieldnames}"
            )

        records = list(reader)

    event_ids = [
        record["event_id"]
        for record in records
        if record["event_id"].strip()
    ]

    event_type_counts = Counter(
        record["event_type"] for record in records
    )

    duplicate_count = len(event_ids) - len(set(event_ids))

    invalid_timestamps = sum(
        record["event_timestamp"] == "not-a-valid-timestamp"
        for record in records
    )

    negative_meters = sum(
        record["meter_kwh"].startswith("-")
        for record in records
    )

    missing_event_ids = sum(
        not record["event_id"].strip()
        for record in records
    )

    unknown_stations = sum(
        record["station_id"] == "UNKNOWN_STATION_999"
        for record in records
    )

    print("\n========== DATASET VERIFICATION ==========")
    print(f"CSV File: {CSV_FILE}")
    print(f"Total Records: {len(records)}")
    print(f"Unique Sessions: {len(set(r['session_id'] for r in records))}")
    print(f"Duplicate Event IDs: {duplicate_count}")

    print("\nEvent Type Distribution:")
    for event_type, count in sorted(event_type_counts.items()):
        print(f"  {event_type}: {count}")

    print("\nInvalid Record Indicators:")
    print(f"  Invalid Timestamps: {invalid_timestamps}")
    print(f"  Negative Meter Values: {negative_meters}")
    print(f"  Missing Event IDs: {missing_event_ids}")
    print(f"  Unknown Stations: {unknown_stations}")

    print("\nCSV schema verification: PASSED")
    print("==========================================\n")


if __name__ == "__main__":
    main()
