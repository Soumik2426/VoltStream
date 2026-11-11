from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import (
    String,
    Integer,
    DateTime,
    ForeignKey,
    Index,
    func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.pipeline_run import PipelineRun


class RejectedRecord(Base):

    __tablename__ = "rejected_records"

    __table_args__ = (
        Index(
            "ix_rejected_records_run_id",
            "run_id"
        ),
        Index(
            "ix_rejected_records_reason",
            "reason_code"
        ),
    )

    reject_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    source_record: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False
    )

    source_file: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    source_row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    reason_code: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    reason_detail: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    run_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("pipeline_runs.run_id"),
        nullable=False
    )

    rejected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    # Many rejected records belong to one pipeline run.
    pipeline_run: Mapped[PipelineRun] = relationship(
        "PipelineRun",
        back_populates="rejected_records"
    )
