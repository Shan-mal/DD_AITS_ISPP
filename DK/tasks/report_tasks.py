from celery import shared_task
from core.database import SessionLocal
import pandas as pd
from datetime import datetime, timedelta
from models.models import ParkingSession
import os

@shared_task
def generate_daily_report():
    db = SessionLocal()
    try:
        yesterday = datetime.utcnow().date() - timedelta(days=1)
        start = datetime(yesterday.year, yesterday.month, yesterday.day)
        end = start + timedelta(days=1)

        sessions = db.query(ParkingSession).filter(
            ParkingSession.exit_time >= start,
            ParkingSession.exit_time < end,
            ParkingSession.status == "completed"
        ).all()

        data = []
        for s in sessions:
            data.append({
                "session_id": s.id,
                "vehicle": s.vehicle.plate_number,
                "entry": s.entry_time,
                "exit": s.exit_time,
                "duration_min": (s.exit_time - s.entry_time).total_seconds() / 60 if s.exit_time else 0,
                "cost": s.total_cost
            })
        df = pd.DataFrame(data)

        os.makedirs("reports", exist_ok=True)
        filename = f"reports/daily_{yesterday.strftime('%Y%m%d')}.csv"
        df.to_csv(filename, index=False)

        return {"status": "ok", "file": filename}
    finally:
        db.close()