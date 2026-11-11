
def reconstruct_session(events: list) -> dict:
    """
    Reconstruct a charging session from its events.

    Events are processed chronologically.
    A session can be COMPLETED without intermediate meter readings.
    Energy consumption is calculated using START and STOP readings.
    Anomalies are detected and returned as reason codes.
    """

    if not events:
        raise ValueError("Cannot reconstruct an empty session")

    # Sort by event timestamp, then event ID for deterministic ordering.
    sorted_events = sorted(
        events,
        key=lambda event: (
            event.event_timestamp,
            event.event_id
        )
    )

    start_event = None
    stop_event = None

    previous_meter = None
    latest_meter = None

    anomaly_reasons = set()

    # All events in one session should belong to the same station.
    station_ids = {
        event.station_id
        for event in sorted_events
        if hasattr(event, "station_id")
    }

    if len(station_ids) > 1:
        anomaly_reasons.add("STATION_MISMATCH")

    for event in sorted_events:

        # Detect events occurring after a STOP event.
        if stop_event is not None:
            anomaly_reasons.add("EVENT_AFTER_STOP")

        if event.event_type == "START":

            if start_event is not None:
                anomaly_reasons.add("MULTIPLE_START_EVENTS")
            else:
                start_event = event

            if previous_meter is not None:
                anomaly_reasons.add("METER_READING_BEFORE_START")

            previous_meter = event.meter_kwh
            latest_meter = event.meter_kwh

        elif event.event_type == "METER_READING":

            if start_event is None:
                anomaly_reasons.add("METER_READING_BEFORE_START")

            if previous_meter is not None:
                if event.meter_kwh < previous_meter:
                    anomaly_reasons.add("DECREASING_METER_READING")

            previous_meter = event.meter_kwh
            latest_meter = event.meter_kwh

        elif event.event_type == "STOP":

            if start_event is None:
                anomaly_reasons.add("STOP_WITHOUT_START")

            if stop_event is not None:
                anomaly_reasons.add("MULTIPLE_STOP_EVENTS")

            if previous_meter is not None:
                if event.meter_kwh < previous_meter:
                    anomaly_reasons.add("DECREASING_METER_READING")

            # Preserve the first STOP event chronologically.
            if stop_event is None:
                stop_event = event

            previous_meter = event.meter_kwh
            latest_meter = event.meter_kwh

    # Determine session status.
    if anomaly_reasons:
        session_status = "ANOMALOUS"

    elif start_event is not None and stop_event is not None:
        session_status = "COMPLETED"

    else:
        session_status = "IN_PROGRESS"

    # Extract session information.
    start_time = (
        start_event.event_timestamp if start_event else None
    )

    end_time = (
        stop_event.event_timestamp if stop_event else None
    )

    start_meter = (
        start_event.meter_kwh if start_event else None
    )

    end_meter = (
        stop_event.meter_kwh if stop_event else None
    )

    energy_consumed = None
    duration_seconds = None

    # Calculate duration whenever both START and STOP exist.
    if start_time is not None and end_time is not None:
        duration_seconds = int(
            (end_time - start_time).total_seconds()
        )

    # Calculate energy only for a valid completed session.
    if (
        session_status == "COMPLETED"
        and start_meter is not None
        and end_meter is not None
    ):
        energy_consumed = end_meter - start_meter

    return {
        "start_time": start_time,
        "end_time": end_time,
        "start_meter_kwh": start_meter,
        "end_meter_kwh": end_meter,
        "energy_consumed_kwh": energy_consumed,
        "duration_seconds": duration_seconds,
        "session_status": session_status,
        "anomaly_reasons": sorted(anomaly_reasons),
        "latest_meter_kwh": latest_meter
    }
