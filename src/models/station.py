from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import String, Numeric, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.models.charging_session import ChargingSession
    from src.models.charging_event import ChargingEvent


class Station(Base):

    __tablename__ = "stations"

    __table_args__ = (
        CheckConstraint(
            "max_power_kw > 0",
            name="ck_station_positive_power"
        ),
    )

    station_id: Mapped[str] = mapped_column(
        String(20),
        primary_key=True
    )

    station_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    max_power_kw: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )

    # One station can have many charging sessions.
    charging_sessions: Mapped[list[ChargingSession]] = relationship(
        "ChargingSession",
        back_populates="station"
    )

    # One station can have many charging events.
    charging_events: Mapped[list[ChargingEvent]] = relationship(
        "ChargingEvent",
        back_populates="station"
    )
