from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Arrival, Line, Trip


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = TestingSession()
    base = datetime(2026, 9, 17, 7, 0)
    db.add(Line(id=1, code="B12", name="城东环线",
                planned_headway_min=8.0, bunch_threshold=3.0, large_threshold=15.0))
    specs = [("T01", "粤A1001", 0), ("T02", "粤A1001", 2), ("T03", "粤A1003", 18)]
    stops = ["起点站", "市民中心", "火车站", "终点站"]
    for trip_no, veh, off in specs:
        t = Trip(line_id=1, trip_no=trip_no,
                 planned_depart=base + timedelta(minutes=off), vehicle_no=veh)
        db.add(t); db.flush()
        for seq, stop in enumerate(stops):
            db.add(Arrival(trip_id=t.id, stop_name=stop, stop_seq=seq,
                           actual_arrive=base + timedelta(minutes=off + seq * 6)))
    db.commit(); db.close()

    yield TestClient(app)
    app.dependency_overrides.clear()


def _center_pair(events, later_trip):
    return next(e for e in events
                if e["stop_name"] == "市民中心" and e["later_trip"] == later_trip)


def test_run_flags_same_vehicle_pair_not_bunching(client):
    evs = client.post("/api/reports/run?line_id=1").json()["events"]
    center = [(e["earlier_trip"], e["later_trip"], e["status"])
              for e in evs if e["stop_name"] == "市民中心"]
    assert center == [("T01", "T02", "same_vehicle"), ("T02", "T03", "large_gap")]


def test_patch_persists_new_vehicle_and_rerun_uses_it(client):
    trips = {t["trip_no"]: t for t in client.get("/api/trips").json()}
    r = client.patch(f"/api/trips/{trips['T02']['id']}", json={"vehicle_no": "粤A2002"})
    assert r.status_code == 200
    assert r.json()["vehicle_no"] == "粤A2002"

    stored = {t["trip_no"]: t["vehicle_no"] for t in client.get("/api/trips").json()}
    assert stored["T02"] == "粤A2002"

    evs = client.post("/api/reports/run?line_id=1").json()["events"]
    # 改号后必须吃新车号重算：T01→T02 异车 2 分钟 → 串车
    assert _center_pair(evs, "T02")["status"] == "bunching"
    # T02→T03 仍异车 → 大间隔，不受改号影响
    assert _center_pair(evs, "T03")["status"] == "large_gap"


def test_patch_back_to_same_vehicle_returns_turnover(client):
    trips = {t["trip_no"]: t for t in client.get("/api/trips").json()}
    client.patch(f"/api/trips/{trips['T02']['id']}", json={"vehicle_no": "粤A2002"})
    client.patch(f"/api/trips/{trips['T02']['id']}", json={"vehicle_no": "粤A1001"})
    evs = client.post("/api/reports/run?line_id=1").json()["events"]
    assert _center_pair(evs, "T02")["status"] == "same_vehicle"


def test_suggestions_exclude_same_vehicle_pair_until_renumbered(client):
    res = client.get("/api/reports/suggestions?line_id=1").json()
    tip_pairs = {(e["earlier_trip"], e["later_trip"]) for e in res["suggestions"]}
    turn_pairs = {(e["earlier_trip"], e["later_trip"]) for e in res["turnovers"]}
    assert ("T01", "T02") not in tip_pairs
    assert ("T01", "T02") in turn_pairs

    trips = {t["trip_no"]: t for t in client.get("/api/trips").json()}
    client.patch(f"/api/trips/{trips['T02']['id']}", json={"vehicle_no": "粤A2002"})
    res = client.get("/api/reports/suggestions?line_id=1").json()
    tip_pairs = {(e["earlier_trip"], e["later_trip"]) for e in res["suggestions"]}
    turn_pairs = {(e["earlier_trip"], e["later_trip"]) for e in res["turnovers"]}
    assert ("T01", "T02") in tip_pairs
    assert ("T01", "T02") not in turn_pairs


def test_timeline_shares_detection_and_never_reds_same_vehicle(client):
    marks = client.get("/api/reports/timeline?line_id=1&stop_name=市民中心").json()["marks"]
    by_trip = {m["trip_no"]: m for m in marks}
    assert by_trip["T01"]["status"] == "first"
    assert by_trip["T02"]["status"] == "same_vehicle"
    assert by_trip["T02"]["vehicle_no"] == "粤A1001"
    assert by_trip["T03"]["status"] == "large_gap"


def test_detection_failure_leaves_participation_set_intact(client, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("检测失败")

    monkeypatch.setattr("app.api.reports.detect_bunching", boom)
    r = client.post("/api/reports/run?line_id=1")
    assert r.status_code == 500

    stored = {t["trip_no"]: t["vehicle_no"] for t in client.get("/api/trips").json()}
    assert stored == {"T01": "粤A1001", "T02": "粤A1001", "T03": "粤A1003"}

    monkeypatch.undo()
    evs = client.post("/api/reports/run?line_id=1").json()["events"]
    assert _center_pair(evs, "T02")["status"] == "same_vehicle"
