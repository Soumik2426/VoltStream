
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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign

from src.database import Base


if TYPE_CHECKING:
    from src.models.station import Station
    from src.models.pipeline_run import PipelineRun
    from src.models.charging_event import ChargingEvent


class ChargingSession(Base):

    __tablename__ = "charging_sessions"

    __table_args__ = (
        CheckConstraint(
            "session_status IN ('IN_PROGRESS', 'COMPLETED', 'ANOMALOUS')",
            name="ck_session_valid_status"
        ),
        CheckConstraint(
            "start_meter_kwh IS NULL OR start_meter_kwh >= 0",
            name="ck_session_nonnegative_start_meter"
        ),
        CheckConstraint(
            "end_meter_kwh IS NULL OR end_meter_kwh >= 0",
            name="ck_session_nonnegative_end_meter"
        ),
        CheckConstraint(
            "energy_consumed_kwh IS NULL OR energy_consumed_kwh >= 0",
            name="ck_session_nonnegative_energy"
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_session_nonnegative_duration"
        ),
        CheckConstraint(
            "start_time IS NULL OR end_time IS NULL OR end_time >= start_time",
            name="ck_session_valid_time_range"
        ),
        Index(
            "ix_charging_sessions_station_start",
            "station_id",
            "start_time"
        ),
    )

    session_id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    station_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stations.station_id"),
        nullable=False
    )

    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    start_meter_kwh: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3),
        nullable=True
    )

    end_meter_kwh: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3),
        nullable=True
    )

    energy_consumed_kwh: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 3),
        nullable=True
    )

    duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True
    )

    session_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="IN_PROGRESS"
    )

    anomaly_reasons: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb")
    )

    last_processed_run_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("pipeline_runs.run_id"),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    # Many sessions belong to one station.
    station: Mapped[Station] = relationship(
        "Station",
        back_populates="charging_sessions"
    )

    # Many sessions can be associated with the last processing run.
    last_processed_run: Mapped[PipelineRun] = relationship(
        "PipelineRun",
        back_populates="charging_sessions"
    )

    events: Mapped[list[ChargingEvent]] = relationship(
        "ChargingEvent",
        primaryjoin=(
            "ChargingSession.session_id == foreign(ChargingEvent.session_id)"
        ),
        back_populates="charging_session",
        viewonly=True,
        order_by="ChargingEvent.event_timestamp"
    )
