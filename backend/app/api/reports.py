import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Arrival, BunchReport, Line, Trip
from app.services.bunch_engine import GapEvent, detect_bunching, events_to_dicts
from app.services.scope_helpers import flatten_marks
router = APIRouter(prefix="/reports", tags=["reports"])

def _detect_events(db: Session, line: Line, stop_name: str | None = None) -> tuple[list[GapEvent], list[dict]]:
    """按当前库里的车号组装参与集并检测。

    车辆号取班次卡片（trips.vehicle_no）的现值：改号后重检必然吃新号，
    不缓存、不沿用旧号配对。
    """
    trips = db.scalars(select(Trip).where(Trip.line_id == line.id)).all()
    trip_no_map = {t.id: t.trip_no for t in trips}
    vehicle_map = {t.id: (t.vehicle_no or "").strip() for t in trips}
    rows = db.scalars(select(Arrival).where(Arrival.trip_id.in_(list(trip_no_map.keys())))).all()
    payload = [{"stop_name": a.stop_name, "trip_no": trip_no_map[a.trip_id],
                "vehicle_no": vehicle_map.get(a.trip_id, ""),
                "actual_arrive": a.actual_arrive}
               for a in rows if stop_name is None or a.stop_name == stop_name]
    events = detect_bunching(payload, line.planned_headway_min, line.bunch_threshold, line.large_threshold)
    return events, payload

@router.get("")
def list_reports(db: Session = Depends(get_db)):
    rows = db.scalars(select(BunchReport).order_by(BunchReport.id.desc())).all()
    return [{"id": r.id, "line_id": r.line_id, "stop_name": r.stop_name,
             "created_at": r.created_at.isoformat(), "events": json.loads(r.summary_json)} for r in rows]

@router.post("/run")
def run_detection(line_id: int, stop_name: str | None = None, db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line: raise HTTPException(404, "线路不存在")
    # 检测全程不改参与集；检测或落库任一步失败都整体回滚，不留半改状态。
    try:
        events, _ = _detect_events(db, line, stop_name)
        data = events_to_dicts(events)
        report = BunchReport(line_id=line_id, stop_name=stop_name or "*", created_at=datetime.utcnow(),
                             summary_json=json.dumps(data, ensure_ascii=False))
        db.add(report); db.commit(); db.refresh(report)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(500, "检测失败，参与集未变更")
    return {"id": report.id, "events": data}

@router.get("/suggestions")
def suggestions(line_id: int, db: Session = Depends(get_db)):
    result = run_detection(line_id=line_id, stop_name=None, db=db)
    all_events = result["events"]
    # 同车接续与串车/大间隔互斥：异常建议只留真正的串车/大间隔，
    # 同车接续单列周转提示，绝不混进异常行。
    tips = [e for e in all_events if e["status"] in ("bunching", "large_gap")]
    turnovers = [e for e in all_events if e["status"] == "same_vehicle"]
    return {"line_id": line_id, "suggestions": tips, "turnovers": turnovers}

@router.get("/timeline")
def timeline(line_id: int, stop_name: str = "市民中心", db: Session = Depends(get_db)):
    line = db.get(Line, line_id)
    if not line: raise HTTPException(404, "线路不存在")
    events, payload = _detect_events(db, line, stop_name)
    rows = sorted((p for p in payload if p["stop_name"] == stop_name), key=lambda p: p["actual_arrive"])
    if not rows: return {"stop_name": stop_name, "marks": []}
    # 时间轴与报告共用同一次检测：每个点标注它作为后班所属相邻对的判定，
    # 同车接续对不标红，保证轴上不再保留这对串车/大间隔。
    event_by_later = {e.later_trip: e for e in events if e.stop_name == stop_name}
    t0 = rows[0]["actual_arrive"]
    span = max((rows[-1]["actual_arrive"] - t0).total_seconds(), 1)
    marks = []
    for r in rows:
        ev = event_by_later.get(r["trip_no"])
        marks.append({"trip_no": r["trip_no"], "vehicle_no": r.get("vehicle_no", ""),
                      "actual_arrive": r["actual_arrive"].isoformat(),
                      "pct": round((r["actual_arrive"] - t0).total_seconds() / span * 100, 2),
                      "status": ev.status if ev else "first",
                      "gap_min": ev.gap_min if ev else None,
                      "paired_trip": ev.earlier_trip if ev else None})
    return {"stop_name": stop_name, "marks": flatten_marks(marks)}
