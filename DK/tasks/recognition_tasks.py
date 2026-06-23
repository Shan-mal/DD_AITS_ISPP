from celery import shared_task
from license_plate.recognizer import LicensePlateRecognizer
from core.database import SessionLocal
from models.models import ParkingSession, Vehicle, ParkingSpot, Tariff, SessionStatus, SpotStatus
from datetime import datetime

recognizer = None

def get_recognizer():
    global recognizer
    if recognizer is None:
        recognizer = LicensePlateRecognizer()
    return recognizer

@shared_task(bind=True, max_retries=3)
def process_entry_camera(self, image_path: str, spot_id: int = None):
    rec = get_recognizer()
    result = rec.run(image_path)

    if not result["success"] or not result["valid_format"]:
        return {"status": "failed", "reason": result.get("error", "Invalid plate")}

    plate = result["plate"]
    db = SessionLocal()
    try:
        vehicle = db.query(Vehicle).filter(Vehicle.plate_number == plate).first()
        if not vehicle:
            vehicle = Vehicle(plate_number=plate)
            db.add(vehicle)
            db.flush()

        active = db.query(ParkingSession).filter(
            ParkingSession.vehicle_id == vehicle.id,
            ParkingSession.status == SessionStatus.active
        ).first()
        if active:
            return {"status": "skipped", "reason": "Active session exists"}

        if spot_id:
            spot = db.query(ParkingSpot).get(spot_id)
            if not spot or spot.status != SpotStatus.free:
                return {"status": "failed", "reason": "Spot not free"}
        else:
            spot = db.query(ParkingSpot).filter(ParkingSpot.status == SpotStatus.free).first()
        if not spot:
            return {"status": "failed", "reason": "No free spots"}

        tariff = db.query(Tariff).filter(Tariff.is_active == True).first()

        session = ParkingSession(
            vehicle_id=vehicle.id,
            spot_id=spot.id,
            entry_time=datetime.utcnow(),
            tariff_id=tariff.id if tariff else None,
            status=SessionStatus.active
        )
        db.add(session)
        spot.status = SpotStatus.occupied
        db.commit()

        return {"status": "success", "session_id": session.id, "plate": plate}
    except Exception as e:
        db.rollback()
        raise self.retry(exc=e, countdown=30)
    finally:
        db.close()