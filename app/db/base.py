from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Explicitly import all models to register with Base
from app.models.user import User
from app.models.event import Event
from app.models.rsvp import RSVP
from app.models.feedback import Feedback
