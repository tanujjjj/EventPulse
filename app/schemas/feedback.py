from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class FeedbackCreate(BaseModel):
    emoji: str
    comment: str | None = None

class FeedbackRead(FeedbackCreate):
    id: UUID
    user_id: UUID
    event_id: UUID
    timestamp: datetime
    pinned: bool
    flagged: bool

    class Config:
        orm_mode = True