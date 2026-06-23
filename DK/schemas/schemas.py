from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class StartParkingRequest(BaseModel):
    plate_number: str = Field(
        ...,
        pattern=r'^[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$',
        description="Госномер РФ (пример: А123БВ77)"
    )

class ParkingSessionOut(BaseModel):
    id: int
    vehicle_id: int
    spot_id: int
    entry_time: datetime
    tariff_id: int
    status: str

    class Config:
        orm_mode = True