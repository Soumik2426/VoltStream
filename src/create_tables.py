from src.database import Base, engine
from src.models import (
    Station,
    PipelineRun,
    ChargingEvent,
    ChargingSession,
    RejectedRecord,
    batch_file
)

# Import models to register their tables with SQLAlchemy metadata.
from src.models import Station, PipelineRun


def create_tables():
    Base.metadata.create_all(bind=engine)

    print("Database tables created successfully!")


if __name__ == "__main__":
    create_tables()