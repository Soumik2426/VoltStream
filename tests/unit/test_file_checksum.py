from src.pipeline import calculate_file_checksum


def test_same_file_generates_same_checksum(tmp_path):
    file_path = tmp_path / "events.csv"

    file_path.write_text(
        "event_id,event_type\n"
        "EVT001,START\n"
        "EVT002,STOP\n"
    )

    checksum1 = calculate_file_checksum(str(file_path))
    checksum2 = calculate_file_checksum(str(file_path))

    assert checksum1 == checksum2


def test_different_content_generates_different_checksum(tmp_path):
    file_path = tmp_path / "events.csv"

    file_path.write_text("event_id\nEVT001\n")
    checksum1 = calculate_file_checksum(str(file_path))

    file_path.write_text("event_id\nEVT002\n")
    checksum2 = calculate_file_checksum(str(file_path))

    assert checksum1 != checksum2
