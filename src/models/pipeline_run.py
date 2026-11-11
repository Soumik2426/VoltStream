from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    Integer,
    Text,
    DateTime,
    CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.charging_event import ChargingEvent
    from src.models.charging_session import ChargingSession
    from src.models.rejected_record import RejectedRecord
    from src.models.batch_file import BatchFile


class PipelineRun(Base):

    __tablename__ = "pipeline_runs"

    __table_args__ = (
        CheckConstraint(
            "input_count >= 0",
            name="ck_run_input_nonnegative"
        ),
        CheckConstraint(
            "accepted_count >= 0",
            name="ck_run_accepted_nonnegative"
        ),
        CheckConstraint(
            "rejected_count >= 0",
            name="ck_run_rejected_nonnegative"
        ),
        CheckConstraint(
            "duplicate_count >= 0",
            name="ck_run_duplicate_nonnegative"
        ),
        CheckConstraint(
            "status IN ('RUNNING', 'SUCCESS', 'FAILED')",
            name="ck_run_valid_status"
        ),
    )

    run_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
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

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="RUNNING"
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # One run can process many charging events.
    charging_events: Mapped[list[ChargingEvent]] = relationship(
        "ChargingEvent",
        back_populates="pipeline_run"
    )

    # One run can generate many rejected records.
    rejected_records: Mapped[list[RejectedRecord]] = relationship(
        "RejectedRecord",
        back_populates="pipeline_run"
    )

    # One run can process multiple files.
    batch_files: Mapped[list[BatchFile]] = relationship(
        "BatchFile",
        back_populates="pipeline_run"
    )

    # Sessions last processed by this run.
    charging_sessions: Mapped[list[ChargingSession]] = relationship(
        "ChargingSession",
        back_populates="last_processed_run"
    )
