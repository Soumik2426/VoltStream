
from sqlalchemy.orm import configure_mappers

from src.models import (
    Station,
    PipelineRun,
    ChargingEvent,
    ChargingSession,
    RejectedRecord,
    BatchFile
)


def verify_relationships():
    configure_mappers()

    models = [
        Station,
        PipelineRun,
        ChargingEvent,
        ChargingSession,
        RejectedRecord,
        BatchFile
    ]

    print("\nAll SQLAlchemy relationships configured successfully!")

    for model in models:
        print(f"\n{model.__name__} relationships:")

        for relationship in model.__mapper__.relationships:
            print(f"  - {relationship.key}")


if __name__ == "__main__":
    verify_relationships()
