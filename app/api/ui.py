from fastapi import APIRouter, Depends, Form, Request, Path, status, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from datetime import datetime, date, timedelta

from app.models.event import Event
from app.models.user import User
from sqlalchemy import func

from app.models.rsvp import RSVP

from app.db.session import AsyncSessionLocal
from app.users import current_active_user
import calendar


import httpx


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@router.get("/dashboard")
async def view_dashboard(request: Request, user: User = Depends(current_active_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Event).where(Event.host_id == user.id))
    events = result.scalars().all()
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "events": events})



@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/auth/jwt/login",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if response.status_code == 204:
            redirect = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
            redirect.set_cookie(
                key="eventpulse",
                value=response.cookies.get("eventpulse"),
                httponly=True,
                max_age=3600,
                path="/",
            )
            return redirect
        raise HTTPException(status_code=401, detail="Invalid credentials")

@router.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
async def register_post(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    full_name: str = Form(None),
    password: str = Form(...),
):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/auth/register",
            json={
                "email": email,
                "username": username,
                "full_name": full_name,
                "password": password
            },
        )
        if response.status_code == 201:
            # auto-login after register
            return await login_post(request, username=email, password=password)
        raise HTTPException(status_code=400, detail="Registration failed")

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("eventpulse")
    return response


@router.get("/calendar")
async def calendar_month_view(
    request: Request,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    today = datetime.utcnow()
    year = today.year
    month = today.month
    month_name = calendar.month_name[month]
    now = datetime.utcnow()

    # Month range
    month_start = datetime(year, month, 1)
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    month_end = datetime(next_year, next_month, 1)

    # Hosted events
    host_result = await db.execute(
        select(Event).where(Event.host_id == user.id, Event.datetime >= month_start, Event.datetime < month_end)
    )
    hosted_events = host_result.scalars().all()

    # RSVPed events
    rsvp_result = await db.execute(select(RSVP).where(RSVP.user_id == user.id))
    rsvped_events = []
    for rsvp in rsvp_result.scalars().all():
        e_result = await db.execute(
            select(Event).where(Event.id == rsvp.event_id, Event.datetime >= month_start, Event.datetime < month_end)
        )
        e = e_result.scalar_one_or_none()
        if e:
            rsvped_events.append(e)

    all_events = {e.id: e for e in hosted_events + rsvped_events}.values()

    for e in all_events:
        e.show_join = e.status == "Live" or (now >= e.datetime and now <= e.datetime + timedelta(hours=1))

    # Build calendar cells
    day_map = {}
    for e in all_events:
        day = e.datetime.day
        day_map.setdefault(day, []).append(e)

    first_weekday, total_days = calendar.monthrange(year, month)
    start_padding = (first_weekday - 0) % 7
    calendar_cells = []
    for _ in range(start_padding):
        calendar_cells.append(None)
    for day in range(1, total_days + 1):
        calendar_cells.append({
            "day": day,
            "events": day_map.get(day, [])
        })

    return templates.TemplateResponse("calendar.html", {
        "request": request,
        "year": year,
        "month_name": month_name,
        "calendar_cells": calendar_cells,
        "now": today
    })