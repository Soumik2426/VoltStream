import logging
import os
from pathlib import Path


def get_logger(name: str) -> logging.Logger:
    """
    Create or retrieve a configured application logger.

    Logs are written to:
    - Console
    - logs/voltstream.log
    """

    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers when the logger is requested again.
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    log_directory = Path("logs")
    log_directory.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler.
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # File handler.
    file_handler = logging.FileHandler(
        log_directory / "voltstream.log",
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
