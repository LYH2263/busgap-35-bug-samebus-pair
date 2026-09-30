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

def _pair(vehicle1: str, vehicle2: str, gap: int):
    base = datetime(2026, 1, 1, 8, 0)
    return [
        {"stop_name": "A", "trip_no": "T1", "vehicle_no": vehicle1, "actual_arrive": base},
        {"stop_name": "A", "trip_no": "T2", "vehicle_no": vehicle2, "actual_arrive": base + timedelta(minutes=gap)},
    ]

def test_renumber_same_to_distinct_reclassifies():
    # 改号前：同一车号 → 同车接续，不报串车
    before = detect_bunching(_pair("V1", "V1", 2), 8.0, 3.0, 15.0)
    assert before[0].status == "same_vehicle"
    # 卡片改成两个车号后重检：必须吃新车号，按异车 2 分钟判串车，不许沿用旧号配对
    after = detect_bunching(_pair("V1", "V2", 2), 8.0, 3.0, 15.0)
    assert after[0].status == "bunching"

def test_renumber_distinct_to_same_reclassifies():
    # 改号前：异车 20 分钟 → 大间隔
    before = detect_bunching(_pair("V1", "V2", 20), 8.0, 3.0, 15.0)
    assert before[0].status == "large_gap"
    # 两班填成同一车号后重检：全程同车不对打，改判同车接续
    after = detect_bunching(_pair("V1", "V1", 20), 8.0, 3.0, 15.0)
    assert after[0].status == "same_vehicle"

def test_same_vehicle_and_threshold_events_are_mutually_exclusive_per_pair():
    base = datetime(2026, 1, 1, 8, 0)
    arrivals = [
        {"stop_name": "A", "trip_no": "T1", "vehicle_no": "V1", "actual_arrive": base},
        {"stop_name": "A", "trip_no": "T2", "vehicle_no": "V1", "actual_arrive": base + timedelta(minutes=2)},
        {"stop_name": "A", "trip_no": "T3", "vehicle_no": "V1", "actual_arrive": base + timedelta(minutes=22)},
    ]
    events = detect_bunching(arrivals, 8.0, 3.0, 15.0)
    # 连续同车：两对都只能是 same_vehicle，不得再出串车或大间隔
    assert [e.status for e in events] == ["same_vehicle", "same_vehicle"]

