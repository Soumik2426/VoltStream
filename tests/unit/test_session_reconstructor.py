
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

from src.transformation.session_reconstructor import reconstruct_session


def create_event(
    event_id,
    event_type,
    timestamp,
    meter_kwh,
    station_id=None
):
    return SimpleNamespace(
        event_id=event_id,
        event_type=event_type,
        event_timestamp=timestamp,
        meter_kwh=meter_kwh,
        station_id=station_id
    )


def test_reconstruct_out_of_order_events():
    start_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    events = [
        create_event("E3", "STOP", start_time + timedelta(minutes=45), 125),
        create_event("E1", "START", start_time, 100),
        create_event("E2", "METER_READING", start_time + timedelta(minutes=20), 115),
    ]

    result = reconstruct_session(events)

    assert result["session_status"] == "COMPLETED"
    assert result["energy_consumed_kwh"] == 25
    assert result["duration_seconds"] == 2700


def test_reconstruct_session_without_stop():
    start_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    events = [
        create_event("E1", "START", start_time, 100)
    ]

    result = reconstruct_session(events)

    assert result["session_status"] == "IN_PROGRESS"
    assert result["end_time"] is None


def test_stop_without_start_is_anomalous():
    timestamp = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    events = [
        create_event("E1", "STOP", timestamp, 125)
    ]

    result = reconstruct_session(events)

    assert result["session_status"] == "ANOMALOUS"
    assert "STOP_WITHOUT_START" in result["anomaly_reasons"]


def test_decreasing_meter_reading_is_anomalous():
    start_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    events = [
        create_event("E1", "START", start_time, 100),
        create_event("E2", "METER_READING", start_time + timedelta(minutes=10), 90),
    ]

    result = reconstruct_session(events)

    assert result["session_status"] == "ANOMALOUS"
    assert "DECREASING_METER_READING" in result["anomaly_reasons"]


def test_start_and_stop_without_intermediate_reading():
    start_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    events = [
        create_event("E1", "START", start_time, 100),
        create_event("E2", "STOP", start_time + timedelta(minutes=45), 125),
    ]

    result = reconstruct_session(events)

    assert result["session_status"] == "COMPLETED"
    assert result["energy_consumed_kwh"] == 25
    assert result["duration_seconds"] == 2700
    assert result["anomaly_reasons"] == []


def test_completed_session_with_unavailable_start_meter():
    start_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    events = [
        create_event("E1", "START", start_time, None),
        create_event("E2", "STOP", start_time + timedelta(minutes=45), 125),
    ]

    result = reconstruct_session(events)

    assert result["session_status"] == "COMPLETED"
    assert result["energy_consumed_kwh"] is None
    assert result["duration_seconds"] == 2700


def test_multiple_start_events_are_anomalous():
    start_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    events = [
        create_event("E1", "START", start_time, 100),
        create_event("E2", "START", start_time + timedelta(minutes=10), 105),
        create_event("E3", "STOP", start_time + timedelta(minutes=30), 120),
    ]

    result = reconstruct_session(events)

    assert result["session_status"] == "ANOMALOUS"
    assert "MULTIPLE_START_EVENTS" in result["anomaly_reasons"]


def test_multiple_stop_events_are_anomalous():
    start_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    events = [
        create_event("E1", "START", start_time, 100),
        create_event("E2", "STOP", start_time + timedelta(minutes=20), 115),
        create_event("E3", "STOP", start_time + timedelta(minutes=30), 120),
    ]

    result = reconstruct_session(events)

    assert result["session_status"] == "ANOMALOUS"
    assert "MULTIPLE_STOP_EVENTS" in result["anomaly_reasons"]


def test_event_after_stop_is_anomalous():
    start_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    events = [
        create_event("E1", "START", start_time, 100),
        create_event("E2", "STOP", start_time + timedelta(minutes=20), 115),
        create_event("E3", "METER_READING", start_time + timedelta(minutes=30), 120),
    ]

    result = reconstruct_session(events)

    assert result["session_status"] == "ANOMALOUS"
    assert "EVENT_AFTER_STOP" in result["anomaly_reasons"]


def test_station_mismatch_is_anomalous():
    start_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    events = [
        create_event("E1", "START", start_time, 100, "STATION_1"),
        create_event(
            "E2",
            "METER_READING",
            start_time + timedelta(minutes=10),
            110,
            "STATION_2"
        ),
        create_event(
            "E3",
            "STOP",
            start_time + timedelta(minutes=30),
            125,
            "STATION_1"
        ),
    ]

    result = reconstruct_session(events)

    assert result["session_status"] == "ANOMALOUS"
    assert "STATION_MISMATCH" in result["anomaly_reasons"]


def test_late_arriving_event_before_stop_is_not_anomalous():
    start_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    events = [
        create_event(
            "E1", "START",
            start_time, 100
        ),
        create_event(
            "E3", "STOP",
            start_time + timedelta(minutes=30), 125
        ),
        create_event(
            "E2", "METER_READING",
            start_time + timedelta(minutes=20), 115
        ),
    ]

    result = reconstruct_session(events)

    assert result["session_status"] == "COMPLETED"
    assert result["energy_consumed_kwh"] == 25
    assert result["duration_seconds"] == 1800
    assert result["anomaly_reasons"] == []