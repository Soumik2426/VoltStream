from src.ingestion.csv_reader import read_csv_file
from src.validation.record_validator import validate_record


if __name__ == "__main__":

    file_path = "data/input/charging_events.csv"

    for record in read_csv_file(file_path):

        errors = validate_record(record)

        if errors:
            print(f"INVALID: {record['event_id']}")
            for error in errors:
                print(error)
        else:
            print(f"VALID: {record['event_id']}")
