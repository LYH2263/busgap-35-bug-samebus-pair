import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Arrival, BunchReport, Line, Trip
from app.services.bunch_engine import detect_bunching, events_to_dicts
from app.services.scope_helpers import flatten_marks
router = APIRouter(prefix="/reports", tags=["reports"])

def _load_line_payload(db: Session, line_id: int, stop_name: str | None = None) -> tuple[Line, list[dict]]:
    """组装检测参与集：车号一律取 Trip 表当前值，班次卡片上写什么就按什么比。"""
    line = db.get(Line, line_id)
    if not line:
        raise HTTPException(404, "线路不存在")
    trips = db.scalars(select(Trip).where(Trip.line_id == line_id)).all()
    trip_no_map = {t.id: t.trip_no for t in trips}
    vehicle_map = {t.id: (t.vehicle_no or "").strip() for t in trips}
    if not trip_no_map:
        return line, []
    arrivals = db.scalars(select(Arrival).where(Arrival.trip_id.in_(list(trip_no_map.keys())))).all()
    payload = [{"stop_name": a.stop_name, "trip_no": trip_no_map[a.trip_id],
                "vehicle_no": vehicle_map.get(a.trip_id, ""),
                "actual_arrive": a.actual_arrive}
               for a in arrivals if stop_name is None or a.stop_name == stop_name]
    return line, payload

@router.get("")
def list_reports(db: Session = Depends(get_db)):
    rows = db.scalars(select(BunchReport).order_by(BunchReport.id.desc())).all()
    return [{"id": r.id, "line_id": r.line_id, "stop_name": r.stop_name,
             "created_at": r.created_at.isoformat(), "events": json.loads(r.summary_json)} for r in rows]

@router.post("/run")
def run_detection(line_id: int, stop_name: str | None = None, db: Session = Depends(get_db)):
    line, payload = _load_line_payload(db, line_id, stop_name)
    # 先纯算事件，状态在引擎内已与同车接续互斥，落库前不得再做任何状态改写。
    events = detect_bunching(payload, line.planned_headway_min, line.bunch_threshold, line.large_threshold)
    data = events_to_dicts(events)
    # 检测与持久化分阶段：落报告失败只回滚报告本身，参与集不留半成品。
    report = BunchReport(line_id=line_id, stop_name=stop_name or "*", created_at=datetime.utcnow(),
                         summary_json=json.dumps(data, ensure_ascii=False))
    db.add(report)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "检测结果保存失败，参与集未改动")
    db.refresh(report)
    return {"id": report.id, "events": data}

@router.get("/suggestions")
def suggestions(line_id: int, db: Session = Depends(get_db)):
    result = run_detection(line_id=line_id, stop_name=None, db=db)
    # 同车接续与串车/大间隔互斥，不作为异常建议保留。
    tips = [e for e in result["events"] if e["status"] in ("bunching", "large_gap")]
    return {"line_id": line_id, "suggestions": tips}

@router.get("/timeline")
def timeline(line_id: int, stop_name: str = "市民中心", db: Session = Depends(get_db)):
    line, payload = _load_line_payload(db, line_id, stop_name)
    arrivals = sorted(payload, key=lambda a: a["actual_arrive"])
    if not arrivals:
        return {"stop_name": stop_name, "marks": []}
    # 与检测同一引擎、同一参与集，取相邻班配对状态，供轴上按真实分档着色。
    pair_status = {e.later_trip: e.status
                   for e in detect_bunching(arrivals, line.planned_headway_min, line.bunch_threshold, line.large_threshold)}
    t0 = arrivals[0]["actual_arrive"]
    span = max((arrivals[-1]["actual_arrive"] - t0).total_seconds(), 1)
    marks = [{"trip_no": a["trip_no"], "vehicle_no": a["vehicle_no"],
              "pair_status": pair_status.get(a["trip_no"], "none"),
              "actual_arrive": a["actual_arrive"].isoformat(),
              "pct": round((a["actual_arrive"] - t0).total_seconds() / span * 100, 2)} for a in arrivals]
    return {"stop_name": stop_name, "marks": flatten_marks(marks)}
