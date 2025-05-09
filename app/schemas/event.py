from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class EventCreate(BaseModel):
    title: str
    description: str
    datetime: datetime
    location: str
    rsvp_deadline: datetime
    max_attendees: int

class EventRead(EventCreate):
    id: UUID
    host_id: UUID
    status: str

    class Config:
        orm_mode = True