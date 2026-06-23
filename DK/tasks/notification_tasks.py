from celery import shared_task
from core.database import SessionLocal
from models.models import ParkingSession

@shared_task
def send_expiry_notification(session_id: int):
    db = SessionLocal()
    try:
        session = db.query(ParkingSession).get(session_id)
        if not session or session.status != "active":
            return
        user = session.vehicle.owner
        if user and user.email:
            # Реальная отправка письма
            print(f"Уведомление для {user.email}: время парковки истекает")
    finally:
        db.close()