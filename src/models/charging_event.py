from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    String,
    Integer,
    Numeric,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Index,
    func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign

from src.database import Base

if TYPE_CHECKING:
    from src.models.station import Station
    from src.models.pipeline_run import PipelineRun
    from src.models.charging_session import ChargingSession


class ChargingEvent(Base):

    __tablename__ = "charging_events"

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('START', 'METER_READING', 'STOP')",
            name="ck_event_valid_type"
        ),
        CheckConstraint(
            "meter_kwh >= 0",
            name="ck_event_nonnegative_meter"
        ),
        CheckConstraint(
            "source_row_number > 0",
            name="ck_event_positive_source_row"
        ),
        Index(
            "ix_charging_events_session_timestamp",
            "session_id",
            "event_timestamp"
        ),
    )

    event_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    # Logical session association, not a mandatory foreign key.
    session_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    station_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stations.station_id"),
        nullable=False
    )

    event_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    event_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    meter_kwh: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
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

    run_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("pipeline_runs.run_id"),
        nullable=False
    )

    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    # Many events belong to one station.
    station: Mapped[Station] = relationship(
        "Station",
        back_populates="charging_events"
    )

    # Many events belong to one pipeline run.
    pipeline_run: Mapped[PipelineRun] = relationship(
        "PipelineRun",
        back_populates="charging_events"
    )

    charging_session: Mapped[ChargingSession | None] = relationship(
        "ChargingSession",
        primaryjoin=(
            "foreign(ChargingEvent.session_id) == ChargingSession.session_id"
        ),
        back_populates="events",
        viewonly=True,
        uselist=False
    )
