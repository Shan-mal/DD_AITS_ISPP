from celery import shared_task
from core.database import SessionLocal
from models.models import ParkingSession, ParkingSpot, SessionStatus, SpotStatus
from sqlalchemy import and_
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@shared_task(bind=True, max_retries=3)
def check_expiring_sessions(self):
    db = next(get_db())
    try:
        now = datetime.utcnow()
        warning_time = now + timedelta(minutes=10)
        sessions = db.query(ParkingSession).filter(
            ParkingSession.status == SessionStatus.active
        ).all()

        for session in sessions:
            if (now - session.entry_time).total_seconds() > 3600:
                from tasks.notification_tasks import send_expiry_notification
                send_expiry_notification.delay(session.id)
        db.commit()
    except Exception as e:
        logger.error(f"Error in check_expiring_sessions: {e}")
        raise self.retry(exc=e, countdown=60)
    finally:
        db.close()

@shared_task
def sync_sensor_data():
    db = next(get_db())
    try:
        spots = db.query(ParkingSpot).filter(ParkingSpot.sensor_id.isnot(None)).all()
        # имитация опроса датчиков
        db.commit()
    finally:
        db.close()

@shared_task
def cleanup_stale_sessions():
    db = next(get_db())
    try:
        stale_time = datetime.utcnow() - timedelta(hours=24)
        stale_sessions = db.query(ParkingSession).filter(
            and_(
                ParkingSession.status == SessionStatus.active,
                ParkingSession.entry_time < stale_time
            )
        ).all()
        for session in stale_sessions:
            session.status = SessionStatus.completed
            session.exit_time = datetime.utcnow()
            spot = session.spot
            if spot:
                spot.status = SpotStatus.free
            tariff = session.tariff
            session.total_cost = tariff.max_daily or (tariff.price_per_minute * 24 * 60)
        db.commit()
        logger.info(f"Cleaned up {len(stale_sessions)} stale sessions")
    finally:
        db.close()