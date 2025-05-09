from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class RSVPRead(BaseModel):
    id: UUID
    event_id: UUID
    user_id: UUID
    check_in_time: datetime | None

    class Config:
        orm_mode = True