from src.ingestion.csv_reader import read_csv_file


if __name__ == "__main__":
    file_path = "data/input/charging_events.csv"

    for record in read_csv_file(file_path):
        print(record)
