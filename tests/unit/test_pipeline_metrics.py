from src.monitoring.metrics import calculate_percentage


def test_calculate_percentage():
    assert calculate_percentage(85, 100) == 85.0


def test_calculate_percentage_with_fraction():
    assert calculate_percentage(1, 3) == 33.33


def test_calculate_percentage_with_zero_total():
    assert calculate_percentage(0, 0) == 0.0


def test_calculate_percentage_with_zero_count():
    assert calculate_percentage(0, 100) == 0.0
