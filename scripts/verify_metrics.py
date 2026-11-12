from pathlib import Path

from src.database import SessionLocal
from src.pipeline import process_csv_file
from src.monitoring.metrics import calculate_run_metrics


def main():
    project_root = Path(__file__).resolve().parent.parent
    csv_file = project_root / "data" / "input" / "charging_events.csv"

    if not csv_file.exists():
        print(f"CSV file not found: {csv_file}")
        return

    db_session = SessionLocal()

    try:
        print(f"Processing file: {csv_file}")

        # Process the CSV and create a real pipeline run.
        result = process_csv_file(db_session, str(csv_file))

        print("\n========== PIPELINE RESULT ==========")
        for key, value in result.items():
            print(f"{key}: {value}")

        # A duplicate file does not create a new pipeline run.
        if result.get("status") == "DUPLICATE_FILE":
            print("\nThis file was already processed.")
            print("Use a different dataset or investigate its existing run.")
            return

        run_id = result["run_id"]

        # Calculate metrics for the newly created pipeline run.
        metrics = calculate_run_metrics(db_session, run_id)

        print("\n========== VOLTSTREAM PIPELINE METRICS ==========")
        for key, value in metrics.items():
            print(f"{key}: {value}")

        print("=================================================")

    except Exception as error:
        print(f"Error: {error}")

    finally:
        db_session.close()


if __name__ == "__main__":
    main()
