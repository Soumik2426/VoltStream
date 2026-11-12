import argparse
import csv
import random

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from src.database import SessionLocal
from src.models.station import Station


# CSV columns must match the ingestion pipeline.
CSV_COLUMNS = [
    "event_id",
    "session_id",
    "station_id",
    "event_type",
    "event_timestamp",
    "meter_kwh"
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIRECTORY = PROJECT_ROOT / "data" / "generated"


# Data-quality issue categories.
INVALID_ISSUES = [
    "INVALID_TIMESTAMP",
    "NEGATIVE_METER",
    "INVALID_EVENT_TYPE",
    "MISSING_EVENT_ID",
    "UNKNOWN_STATION"
]

ANOMALY_ISSUES = [
    "DECREASING_METER",
    "STOP_WITHOUT_START",
    "MULTIPLE_START_EVENTS",
    "MULTIPLE_STOP_EVENTS"
]


# Illustrative distribution. These percentages are configurable.
DEFAULT_DISTRIBUTION = {
    "valid": 70,
    "invalid": 15,
    "anomalous": 10,
    "duplicate": 5
}


def get_registered_stations():
    """Fetch registered charging stations from PostgreSQL."""

    db_session = SessionLocal()

    try:
        stations = db_session.scalars(
            select(Station)
        ).all()

        return [
            {
                "station_id": station.station_id,
                "max_power_kw": float(station.max_power_kw)
            }
            for station in stations
        ]

    finally:
        db_session.close()


def generate_charging_session(station, session_number, rng, seed):
    """
    Generate one complete charging session:
    START -> METER_READING -> STOP.

    Seed-based IDs ensure that different generated datasets
    do not reuse previously generated session/event IDs.
    """

    session_id = f"SES_GEN_S{seed}_{session_number:08d}"

    start_time = datetime(
        2026, 11, 1, 8, 0,
        tzinfo=timezone.utc
    ) + timedelta(
        minutes=rng.randint(0, 30 * 24 * 60)
    )

    duration_minutes = rng.randint(30, 180)

    energy_consumed = round(
        rng.uniform(5.0, 40.0),
        3
    )

    intermediate_energy = round(
        energy_consumed * rng.uniform(0.3, 0.7),
        3
    )

    middle_time = start_time + timedelta(
        minutes=duration_minutes // 2
    )

    stop_time = start_time + timedelta(
        minutes=duration_minutes
    )

    def format_timestamp(value):
        return value.isoformat().replace("+00:00", "Z")

    return [
        {
            "event_id": f"EVT_GEN_S{seed}_{session_number:08d}_01",
            "session_id": session_id,
            "station_id": station["station_id"],
            "event_type": "START",
            "event_timestamp": format_timestamp(start_time),
            "meter_kwh": "0.000"
        },
        {
            "event_id": f"EVT_GEN_S{seed}_{session_number:08d}_02",
            "session_id": session_id,
            "station_id": station["station_id"],
            "event_type": "METER_READING",
            "event_timestamp": format_timestamp(middle_time),
            "meter_kwh": f"{intermediate_energy:.3f}"
        },
        {
            "event_id": f"EVT_GEN_S{seed}_{session_number:08d}_03",
            "session_id": session_id,
            "station_id": station["station_id"],
            "event_type": "STOP",
            "event_timestamp": format_timestamp(stop_time),
            "meter_kwh": f"{energy_consumed:.3f}"
        }
    ]


def inject_data_quality_issue(events, issue_type, rng):
    """Introduce a controlled data-quality issue."""

    corrupted_events = [
        event.copy() for event in events
    ]

    if issue_type == "INVALID_TIMESTAMP":
        target = corrupted_events[1]
        target["event_timestamp"] = "not-a-valid-timestamp"

    elif issue_type == "NEGATIVE_METER":
        target = corrupted_events[1]
        target["meter_kwh"] = "-25.500"

    elif issue_type == "INVALID_EVENT_TYPE":
        target = corrupted_events[1]
        target["event_type"] = "UNKNOWN_EVENT"

    elif issue_type == "MISSING_EVENT_ID":
        target = corrupted_events[1]
        target["event_id"] = ""

    elif issue_type == "UNKNOWN_STATION":
        for event in corrupted_events:
            event["station_id"] = "UNKNOWN_STATION_999"

    elif issue_type == "DECREASING_METER":
        # Intermediate reading exceeds the final reading.
        corrupted_events[1]["meter_kwh"] = "9999.999"

    elif issue_type == "STOP_WITHOUT_START":
        # Replace START with METER_READING.
        corrupted_events[0]["event_type"] = "METER_READING"

    elif issue_type == "MULTIPLE_START_EVENTS":
        corrupted_events[1]["event_type"] = "START"

    elif issue_type == "MULTIPLE_STOP_EVENTS":
        corrupted_events[1]["event_type"] = "STOP"

    else:
        raise ValueError(
            f"Unsupported issue type: {issue_type}"
        )

    return corrupted_events


def generate_records(
    record_count,
    seed=42,
    distribution=None
):
    """
    Generate a reproducible dataset containing valid,
    invalid, anomalous and duplicate events.

    The requested count is rounded down to a multiple of 3
    because each base session contains three events.

    Duplicate scenarios add one additional event.
    """

    if record_count < 3:
        raise ValueError("Record count must be at least 3.")

    rng = random.Random(seed)

    distribution = (
        DEFAULT_DISTRIBUTION.copy()
        if distribution is None
        else distribution.copy()
    )

    if set(distribution) != {
        "valid", "invalid", "anomalous", "duplicate"
    }:
        raise ValueError("Invalid distribution categories.")

    if any(
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or value < 0
        for value in distribution.values()
    ):
        raise ValueError(
            "Distribution values must be non-negative."
        )

    if abs(sum(distribution.values()) - 100) > 0.0001:
        raise ValueError(
            "Distribution percentages must total 100."
        )

    stations = get_registered_stations()

    if not stations:
        raise RuntimeError(
            "No registered charging stations found in PostgreSQL."
        )

    # Generate complete three-event sessions.
    session_count = record_count // 3
    actual_record_count = session_count * 3

    valid_sessions = round(
        session_count * distribution["valid"] / 100
    )

    invalid_sessions = round(
        session_count * distribution["invalid"] / 100
    )

    anomalous_sessions = round(
        session_count * distribution["anomalous"] / 100
    )

    # Remaining sessions become duplicate scenarios.
    duplicate_sessions = (
        session_count
        - valid_sessions
        - invalid_sessions
        - anomalous_sessions
    )

    categories = (
        ["valid"] * valid_sessions
        + ["invalid"] * invalid_sessions
        + ["anomalous"] * anomalous_sessions
        + ["duplicate"] * duplicate_sessions
    )

    rng.shuffle(categories)

    records = []

    category_counts = {
        "valid": 0,
        "invalid": 0,
        "anomalous": 0,
        "duplicate": 0
    }

    for session_number, category in enumerate(
        categories,
        start=1
    ):

        station = rng.choice(stations)

        events = generate_charging_session(
            station,
            session_number,
            rng,
            seed
        )

        category_counts[category] += 1

        if category == "invalid":
            issue = rng.choice(INVALID_ISSUES)

            events = inject_data_quality_issue(
                events,
                issue,
                rng
            )

        elif category == "anomalous":
            issue = rng.choice(ANOMALY_ISSUES)

            events = inject_data_quality_issue(
                events,
                issue,
                rng
            )

        elif category == "duplicate":
            # Retain original event and add an exact duplicate.
            duplicate = events[-1].copy()
            events.append(duplicate)

        records.extend(events)

    # Shuffle records to simulate out-of-order event arrival.
    rng.shuffle(records)

    return records, category_counts, actual_record_count


def write_csv(records, output_file):
    """Write generated records to CSV."""

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with output_file.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=CSV_COLUMNS
        )

        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(
        description="VoltStream EV charging event generator"
    )

    parser.add_argument(
        "--records",
        type=int,
        default=300,
        help="Approximate number of events to generate."
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility."
    )

    parser.add_argument(
        "--output",
        type=str,
        default="charging_events_generated.csv",
        help="Output CSV filename."
    )

    args = parser.parse_args()

    if Path(args.output).name != args.output:
        parser.error("--output must be a filename, not a path.")

    output_file = OUTPUT_DIRECTORY / args.output

    records, category_counts, actual_count = generate_records(
        record_count=args.records,
        seed=args.seed
    )

    write_csv(records, output_file)

    print("\n========== VOLTSTREAM DATA GENERATOR ==========")
    print(f"Requested records: {args.records}")
    print(f"Base records before duplicate injection: {actual_count}")
    print(f"Generated records: {len(records)}")
    print(f"Output file: {output_file}")
    print(f"Random seed: {args.seed}")

    print("\nGenerated session categories:")

    for category, count in category_counts.items():
        print(f"{category}: {count}")

    print("================================================")


if __name__ == "__main__":
    main()
