
import csv
from pathlib import Path
from typing import Iterator


REQUIRED_COLUMNS = {
    "event_id",
    "session_id",
    "station_id",
    "event_type",
    "event_timestamp",
    "meter_kwh",
}


def read_csv_file(file_path: str) -> Iterator[dict]:
    """
    Read charging events from a CSV file.

    Returns one dictionary per data row, along with
    source filename and source row number.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    if not path.is_file():
        raise ValueError(f"Input path is not a file: {path}")

    with path.open(
        mode="r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError("CSV file is empty or has no header")

        # Normalize column names by removing surrounding whitespace.
        headers = [
            header.strip() if header else header
            for header in reader.fieldnames
        ]

        # Check for duplicate column names after normalization.
        if len(headers) != len(set(headers)):
            raise ValueError("CSV contains duplicate column names")

        if any(not header for header in headers):
            raise ValueError("CSV contains a blank column name")

        missing_columns = REQUIRED_COLUMNS - set(headers)

        if missing_columns:
            raise ValueError(
                f"Missing required columns: {sorted(missing_columns)}"
            )

        # Use normalized headers for subsequent row processing.
        reader.fieldnames = headers

        for row_number, row in enumerate(reader, start=2):

            # Extra values without corresponding column names
            # indicate a malformed row.
            if None in row:
                row["_ingestion_error"] = "EXTRA_COLUMNS"

            row["_source_file"] = path.name
            row["_source_row_number"] = row_number

            yield row
