import os
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SEED_ON_EMPTY", "false")

from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Arrival, Line, Trip


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # 不用上下文管理器，避免触发连默认库的 lifespan 建表/播种
    c = TestClient(app)
    yield c, TestingSession
    app.dependency_overrides.clear()


def _seed(db, t1_vehicle, t2_vehicle, gap_min=2):
    line = Line(code="B12", name="测试线", planned_headway_min=8.0,
                bunch_threshold=3.0, large_threshold=15.0)
    db.add(line); db.flush()
    base = datetime(2026, 1, 1, 8, 0)
    t1 = Trip(line_id=line.id, trip_no="T1", planned_depart=base, vehicle_no=t1_vehicle)
    t2 = Trip(line_id=line.id, trip_no="T2", planned_depart=base + timedelta(minutes=gap_min),
              vehicle_no=t2_vehicle)
    db.add_all([t1, t2]); db.flush()
    for seq, (trip, off) in enumerate([(t1, 0), (t2, gap_min)]):
        db.add(Arrival(trip_id=trip.id, stop_name="市民中心", stop_seq=seq,
                       actual_arrive=base + timedelta(minutes=off)))
    db.commit()
    return line.id, t1.id, t2.id


def _run(client, line_id):
    r = client.post(f"/api/reports/run?line_id={line_id}")
    assert r.status_code == 200, r.text
    events = r.json()["events"]
    assert len(events) == 1
    return events[0]


def test_same_vehicle_pair_is_same_vehicle_not_bunching(client):
    c, Session = client
    db = Session(); line_id, _, _ = _seed(db, "V1", "V1", gap_min=2); db.close()
    assert _run(c, line_id)["status"] == "same_vehicle"


def test_same_vehicle_pair_is_same_vehicle_not_large_gap(client):
    c, Session = client
    db = Session(); line_id, _, _ = _seed(db, "V1", "V1", gap_min=20); db.close()
    assert _run(c, line_id)["status"] == "same_vehicle"


def test_different_vehicles_adjacent_follow_threshold(client):
    c, Session = client
    db = Session(); line_id, _, _ = _seed(db, "V1", "V2", gap_min=2); db.close()
    assert _run(c, line_id)["status"] == "bunching"


def test_change_vehicle_then_detect_recomputes_with_new_no(client):
    c, Session = client
    db = Session(); line_id, _, t2_id = _seed(db, "V1", "V1", gap_min=2); db.close()

    # 改号前：同车接续
    assert _run(c, line_id)["status"] == "same_vehicle"

    # 改成不同车号后，本次检测必须按新车号重算为串车，不得沿用旧 V1 配对
    r = c.patch(f"/api/trips/{t2_id}", json={"vehicle_no": "V2"})
    assert r.status_code == 200, r.text
    assert r.json()["vehicle_no"] == "V2"
    assert _run(c, line_id)["status"] == "bunching"

    # 再改回同号，立即恢复同车接续
    r = c.patch(f"/api/trips/{t2_id}", json={"vehicle_no": "V1"})
    assert r.status_code == 200, r.text
    assert _run(c, line_id)["status"] == "same_vehicle"

    # 库中确为最新车号
    db = Session()
    assert db.get(Trip, t2_id).vehicle_no == "V1"
    db.close()


def test_suggestions_exclude_same_vehicle(client):
    c, Session = client
    db = Session(); line_id, _, _ = _seed(db, "V1", "V1", gap_min=2); db.close()
    r = c.get(f"/api/reports/suggestions?line_id={line_id}")
    assert r.status_code == 200, r.text
    statuses = [e["status"] for e in r.json()["suggestions"]]
    assert "same_vehicle" not in statuses
    assert statuses == []


def test_timeline_pair_status_matches_detection(client):
    c, Session = client
    db = Session(); line_id, _, t2_id = _seed(db, "V1", "V1", gap_min=2); db.close()

    r = c.get(f"/api/reports/timeline?line_id={line_id}&stop_name=市民中心")
    assert r.status_code == 200, r.text
    marks = {m["trip_no"]: m for m in r.json()["marks"]}
    assert marks["T1"]["pair_status"] == "none"
    assert marks["T2"]["pair_status"] == "same_vehicle"
    assert marks["T2"]["vehicle_no"] == "V1"

    c.patch(f"/api/trips/{t2_id}", json={"vehicle_no": "V2"})
    r = c.get(f"/api/reports/timeline?line_id={line_id}&stop_name=市民中心")
    marks = {m["trip_no"]: m for m in r.json()["marks"]}
    assert marks["T2"]["pair_status"] == "bunching"
    assert marks["T2"]["vehicle_no"] == "V2"
