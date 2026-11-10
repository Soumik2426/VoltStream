import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

load_dotenv()

DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT")),
    database=os.getenv("DB_NAME")
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)


def test_connection():
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT version()")
            )

            print("Database connected successfully!")
            print(result.scalar())

    except Exception as e:
        print("Database connection failed!")
        print(e)


if __name__ == "__main__":
    test_connection()