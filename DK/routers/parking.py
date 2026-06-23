from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from core.database import get_db
from models.models import User, Vehicle, ParkingSpot, Tariff, ParkingSession, SessionStatus
from schemas.schemas import StartParkingRequest, ParkingSessionOut
from dependencies import get_current_user
from tasks.parking_tasks import check_expiring_sessions  # если нужно ручное планирование
import datetime

router = APIRouter(prefix="/parking", tags=["parking"])

@router.post("/start", response_model=ParkingSessionOut)
async def start_parking_session(
    request: StartParkingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    vehicle = db.query(Vehicle).filter(
        Vehicle.plate_number == request.plate_number
    ).first()

    if not vehicle:
        vehicle = Vehicle(
            user_id=current_user.id,
            plate_number=request.plate_number.upper()
        )
        db.add(vehicle)
        db.flush()
    else:
        if vehicle.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Автомобиль привязан к другому пользователю"
            )

    active_session = db.query(ParkingSession).filter(
        and_(
            ParkingSession.vehicle_id == vehicle.id,
            ParkingSession.status == SessionStatus.active
        )
    ).first()
    if active_session:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Для данного автомобиля уже есть активная сессия"
        )

    free_spot = db.query(ParkingSpot).filter(
        ParkingSpot.status == "free"
    ).first()
    if not free_spot:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Нет свободных мест"
        )

    active_tariff = db.query(Tariff).filter(Tariff.is_active == True).first()
    if not active_tariff:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не настроены активные тарифы"
        )

    session = ParkingSession(
        vehicle_id=vehicle.id,
        spot_id=free_spot.id,
        entry_time=datetime.datetime.utcnow(),
        tariff_id=active_tariff.id,
        status=SessionStatus.active
    )
    db.add(session)

    free_spot.status = "occupied"
    db.add(free_spot)

    db.commit()
    db.refresh(session)

    # Запуск напоминания (можно отложить или использовать beat)
    # from tasks.notification_tasks import send_expiry_notification
    # send_expiry_notification.apply_async(args=[session.id], countdown=600)

    return session