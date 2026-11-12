from pathlib import Path

from src.database import SessionLocal
from src.pipeline import process_csv_file
from src.monitoring.metrics import calculate_run_metrics
from src.models.batch_file import BatchFile


def main():
    csv_file = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "generated"
        / "charging_events_generated.csv"
    )

    if not csv_file.exists():
        raise FileNotFoundError(
            f"Dataset not found: {csv_file}"
        )

    db_session = SessionLocal()

    try:
        print("\nStarting VoltStream pipeline...")
        print(f"Input file: {csv_file}")

        result = process_csv_file(
            db_session,
            str(csv_file)
        )

        # Handle dictionary responses.
        if isinstance(result, dict):

            if result.get("status") == "DUPLICATE_FILE":
                print("\nFile was already processed.")

                batch_file_id = result.get("batch_file_id")

                existing_batch = db_session.get(
                    BatchFile,
                    batch_file_id
                )

                if existing_batch is None:
                    print("Existing batch record not found.")
                    return

                run_id = existing_batch.run_id

            else:
                # Normal successful or partial-success response.
                run_id = result.get("run_id")

                print("\nPipeline processing completed.")
                print(f"Batch ID: {result.get('batch_file_id')}")
                print(f"Status: {result.get('status')}")
                print(f"Input records: {result.get('input_count')}")
                print(f"Accepted: {result.get('accepted_count')}")
                print(f"Rejected: {result.get('rejected_count')}")
                print(f"Duplicates: {result.get('duplicate_count')}")

        else:
            # Handle a legacy string run ID.
            run_id = result

        if not run_id:
            print("Unable to determine the pipeline run ID.")
            return

        print(f"\nRun ID: {run_id}")

        # Calculate metrics using the actual run ID.
        metrics = calculate_run_metrics(
            db_session,
            run_id
        )

        print("\n========== PIPELINE METRICS ==========")

        for key, value in metrics.items():
            print(f"{key}: {value}")

        print("======================================\n")

    finally:
        db_session.close()


if __name__ == "__main__":
    main()
