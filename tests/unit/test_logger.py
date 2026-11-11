import logging

from src.monitoring.logger import get_logger


def test_get_logger_returns_logger():
    logger = get_logger("voltstream.test")

    assert isinstance(logger, logging.Logger)


def test_logger_level_is_info():
    logger = get_logger("voltstream.level_test")

    assert logger.level == logging.INFO


def test_logger_does_not_duplicate_handlers():
    logger = get_logger("voltstream.handler_test")

    initial_handler_count = len(logger.handlers)

    get_logger("voltstream.handler_test")

    assert len(logger.handlers) == initial_handler_count


def test_logger_does_not_propagate():
    logger = get_logger("voltstream.propagation_test")

    assert logger.propagate is False
