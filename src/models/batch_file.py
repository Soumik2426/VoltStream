from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    TIMESTAMP,
    Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.pipeline_run import PipelineRun


class BatchFile(Base):

    __tablename__ = "batch_files"

    batch_file_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    run_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("pipeline_runs.run_id"),
        nullable=False
    )

    source_file: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    file_checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )

    file_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    input_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    accepted_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    rejected_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    duplicate_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "file_status IN ('PROCESSING', 'SUCCESS', 'PARTIAL_SUCCESS', 'FAILED')",
            name="ck_batch_files_status"
        ),
        CheckConstraint(
            "input_count >= 0 AND accepted_count >= 0 "
            "AND rejected_count >= 0 AND duplicate_count >= 0",
            name="ck_batch_files_non_negative_counts"
        ),
        Index("ix_batch_files_checksum", "file_checksum"),
        Index("ix_batch_files_run_id", "run_id"),
    )

    # Many batch-file attempts belong to one pipeline run.
    pipeline_run: Mapped[PipelineRun] = relationship(
        "PipelineRun",
        back_populates="batch_files"
    )
