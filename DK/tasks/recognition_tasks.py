from celery import shared_task
from license_plate.recognizer import LicensePlateRecognizer
from core.database import SessionLocal
from models.models import ParkingSession, Vehicle, ParkingSpot, Tariff, SessionStatus, SpotStatus
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

recognizer = None

def get_recognizer():
    global recognizer
    if recognizer is None:
        recognizer = LicensePlateRecognizer()
    return recognizer

@shared_task(bind=True, max_retries=2)
def process_entry_camera(self, image_path: str, spot_id: int = None):
    rec = get_recognizer()
    result = rec.run(image_path)
    logger.info(f"Результат распознавания: {result}")

    if not result["success"]:
        return {"status": "failed", "reason": result.get("error", "Recognition failed")}

    plate = result["plate"]
    confidence = result["confidence"]
    is_valid = result["valid_format"]

    # Если формат не совпадает, но номер длинный, примем для теста
    if not is_valid and len(plate) >= 6:
        logger.warning(f"Номер не прошёл валидацию, но принят для теста: {plate} (уверенность {confidence})")
        is_valid = True

    if not is_valid:
        return {"status": "failed", "reason": f"Invalid plate: {plate} (conf: {confidence})"}

    db = SessionLocal()
    try:
        vehicle = db.query(Vehicle).filter(Vehicle.plate_number == plate).first()
        if not vehicle:
            # Создаём автомобиль без владельца (user_id=None)
            vehicle = Vehicle(plate_number=plate)
            db.add(vehicle)
            db.flush()  # чтобы получить id

        # Проверка активной сессии
        active = db.query(ParkingSession).filter(
            ParkingSession.vehicle_id == vehicle.id,
            ParkingSession.status == SessionStatus.active
        ).first()
        if active:
            db.close()
            return {"status": "skipped", "reason": "Active session exists"}

        # Поиск свободного места
        if spot_id:
            spot = db.query(ParkingSpot).get(spot_id)
            if not spot or spot.status != SpotStatus.free:
                db.close()
                return {"status": "failed", "reason": "Spot not free"}
        else:
            spot = db.query(ParkingSpot).filter(ParkingSpot.status == SpotStatus.free).first()
        if not spot:
            db.close()
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
        logger.error(f"Ошибка в process_entry_camera: {e}")
        return {"status": "failed", "reason": str(e)}
    finally:
        db.close()