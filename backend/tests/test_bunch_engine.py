from datetime import datetime, timedelta
from app.services.bunch_engine import classify_gap, detect_bunching

def test_classify_bunching():
    assert classify_gap(2.0, 8.0, 3.0, 15.0)[0] == "bunching"

def test_classify_large():
    assert classify_gap(16.0, 8.0, 3.0, 15.0)[0] == "large_gap"

def test_classify_normal():
    assert classify_gap(8.0, 8.0, 3.0, 15.0)[0] == "normal"

def test_detect_bunching_events():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "A", "trip_no": "T1", "vehicle_no": "V1", "actual_arrive": base},
        {"stop_name": "A", "trip_no": "T2", "vehicle_no": "V2", "actual_arrive": base + timedelta(minutes=2)},
        {"stop_name": "A", "trip_no": "T3", "vehicle_no": "V3", "actual_arrive": base + timedelta(minutes=20)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0)
    assert len(events) == 2
    assert events[0].status == "bunching"
    assert events[1].status == "large_gap"

def test_same_vehicle_turnover_not_bunching():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "A", "trip_no": "T1", "vehicle_no": "V1", "actual_arrive": base},
        {"stop_name": "A", "trip_no": "T2", "vehicle_no": "V1", "actual_arrive": base + timedelta(minutes=2)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0)
    assert len(events) == 1
    assert events[0].status == "same_vehicle"

def test_same_vehicle_turnover_not_large_gap():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "A", "trip_no": "T1", "vehicle_no": "V1", "actual_arrive": base},
        {"stop_name": "A", "trip_no": "T2", "vehicle_no": "V1", "actual_arrive": base + timedelta(minutes=20)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0)
    assert len(events) == 1
    assert events[0].status == "same_vehicle"

def test_same_vehicle_pair_isolated_but_neighbor_still_judged():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "A", "trip_no": "T1", "vehicle_no": "V1", "actual_arrive": base},
        {"stop_name": "A", "trip_no": "T2", "vehicle_no": "V1", "actual_arrive": base + timedelta(minutes=2)},
        {"stop_name": "A", "trip_no": "T3", "vehicle_no": "V3", "actual_arrive": base + timedelta(minutes=18)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0)
    assert [e.status for e in events] == ["same_vehicle", "large_gap"]

def test_empty_vehicle_still_judged_by_thresholds():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "A", "trip_no": "T1", "vehicle_no": "", "actual_arrive": base},
        {"stop_name": "A", "trip_no": "T2", "vehicle_no": "", "actual_arrive": base + timedelta(minutes=2)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0)
    assert len(events) == 1
    assert events[0].status == "bunching"

def test_missing_vehicle_key_still_judged_by_thresholds():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "A", "trip_no": "T1", "actual_arrive": base},
        {"stop_name": "A", "trip_no": "T2", "actual_arrive": base + timedelta(minutes=2)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0)
    assert len(events) == 1
    assert events[0].status == "bunching"
