from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from app.models.user import User
from app.schemas.user import UserRead, UserCreate, UserUpdate
from app.users import fastapi_users, auth_backend
from app.api import events
from app.api import ui
from app.db.session import engine
from app.db.base import Base 


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="EventPulse – Real-Time RSVP & Feedback Platform")

templates = Jinja2Templates(directory="app/templates")


app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"]
)

# Auth: register
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"]
)

# Auth: /auth/users/me and profile routes
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/auth",
    tags=["auth"]
)
@app.get("/")
def root():
    return {"message": "Welcome to EventPulse!"}

app.include_router(events.router, prefix="/events", tags=["events"])

app.include_router(ui.router)
