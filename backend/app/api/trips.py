from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Trip
router = APIRouter(prefix="/trips", tags=["trips"])

class VehicleUpdate(BaseModel):
    vehicle_no: str

def trip_dict(r: Trip) -> dict:
    return {"id": r.id, "line_id": r.line_id, "trip_no": r.trip_no,
            "planned_depart": r.planned_depart.isoformat(), "vehicle_no": r.vehicle_no}

@router.get("")
def list_trips(line_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Trip).order_by(Trip.planned_depart)
    if line_id is not None: q = q.where(Trip.line_id == line_id)
    return [trip_dict(r) for r in db.scalars(q).all()]

@router.patch("/{trip_id}")
def update_vehicle(trip_id: int, body: VehicleUpdate, db: Session = Depends(get_db)):
    trip = db.get(Trip, trip_id)
    if not trip: raise HTTPException(404, "班次不存在")
    # 车辆号必须真实落库：检测时读的是 Trip.vehicle_no，不落库就会继续按旧号配对。
    new_vehicle = (body.vehicle_no or "").strip()
    try:
        trip.vehicle_no = new_vehicle
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(500, "车辆号保存失败，参与集未改动")
    db.refresh(trip)
    return trip_dict(trip)
