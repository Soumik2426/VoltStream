from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from src.database import SessionLocal
from src.models import Station, PipelineRun, BatchFile
from src.pipeline import register_batch_file


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_register_new_batch_file(db_session, tmp_path):
    file_path = tmp_path / "events.csv"
    file_path.write_text("event_id,event_type\nEVT001,START\n")

    pipeline_run, batch_file, is_duplicate = register_batch_file(
        db_session,
        str(file_path)
    )

    assert pipeline_run is not None
    assert batch_file is not None
    assert is_duplicate is False
    assert batch_file.file_checksum != "PENDING"
    assert batch_file.file_status == "PROCESSING"


def test_register_duplicate_file(db_session, tmp_path):
    file_path = tmp_path / "events.csv"
    file_path.write_text("event_id,event_type\nEVT001,START\n")

    first_run, first_batch, first_duplicate = register_batch_file(
        db_session,
        str(file_path)
    )

    db_session.flush()

    second_run, second_batch, second_duplicate = register_batch_file(
        db_session,
        str(file_path)
    )

    assert first_duplicate is False
    assert second_duplicate is True
    assert second_run is None
    assert second_batch.batch_file_id == first_batch.batch_file_id


def test_register_missing_file_raises_error(db_session, tmp_path):
    missing_file = tmp_path / "missing.csv"

    with pytest.raises(FileNotFoundError):
        register_batch_file(db_session, str(missing_file))
