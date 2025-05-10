# app/models/registry.py
from app.db.base import Base
from app.models.user import User
from app.models.event import Event
from app.models.rsvp import RSVP
from app.models.feedback import Feedback

__all__ = ["User", "Event", "RSVP", "Feedback"]

# This ensures all models are registered with SQLAlchemy
def register_models():
    # Just importing them is enough to register
    pass