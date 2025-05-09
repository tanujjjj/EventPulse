from fastapi import APIRouter, Depends, Form, Request, Path, status, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from datetime import datetime, date, timedelta

from app.models.event import Event
from app.models.user import User
from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackCreate
import collections
from sqlalchemy import func


from app.db.session import AsyncSessionLocal
from app.users import current_active_user
from collections import Counter

import httpx

from app.schemas.event import EventCreate, EventRead
from app.models.rsvp import RSVP


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

@router.post("/", response_model=EventRead)
async def create_event(
    event: EventCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    db_event = Event(**event.dict(), host_id=user.id)
    db.add(db_event)
    await db.commit()
    await db.refresh(db_event)
    return db_event

@router.get("/mine", response_model=list[EventRead])
async def get_my_events(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_active_user),
):
    result = await db.execute(select(Event).where(Event.host_id == user.id))
    events = result.scalars().all()
    return events


@router.get("/create")
async def event_form(request: Request, user: User = Depends(current_active_user)):
    return templates.TemplateResponse("event_create.html", {"request": request, "user": user, "datetime": datetime.utcnow()})

@router.post("/create")
async def submit_event(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    datetime: datetime = Form(...),
    location: str = Form(...),
    rsvp_deadline: datetime = Form(...),
    max_attendees: int = Form(...),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    if rsvp_deadline > datetime:
        return JSONResponse(
            status_code=400,
            content={
                "error": "RSVP deadline must be before event start time",
                "type": "validation_error"
            }
        )

    now = datetime.utcnow()
    if now > datetime:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Event time must be in the future",
                "type": "validation_error"
            }
        )
        
    new_event = Event(
        title=title,
        description=description,
        datetime=datetime,
        location=location,
        rsvp_deadline=rsvp_deadline,
        max_attendees=max_attendees,
        host_id=user.id
    )
    
    db.add(new_event)
    await db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/{event_id}/live")
async def live_feedback_page(
    request: Request,
    event_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.status == "Closed":
        return {"msg": "Event is closed"}
    if event.status == "Scheduled" and user.id == event.host_id:
        event.status = "Live"
        await db.commit()
    if user.id != event.host_id:
        rsvp_result = await db.execute(select(RSVP).where(RSVP.event_id == event_id, RSVP.user_id == user.id))
        rsvp = rsvp_result.scalar_one_or_none()
        if not rsvp:
            raise HTTPException(status_code=403, detail="You must RSVP to view this page or Request the host to check you in")
        if not rsvp.check_in_time:
            raise HTTPException(status_code=403, detail="You must check in to view this page")
    
    return templates.TemplateResponse("event_live.html", {
        "request": request,
        "event": event,
        "user": user
    })

@router.post("/{event_id}/feedback")
async def submit_feedback(
    event_id: UUID,
    emoji: str = Form(...),
    comment: str = Form(""),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    feedback = Feedback(event_id=event_id, user_id=user.id, emoji=emoji, comment=comment)
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    return HTMLResponse(content=f"""
  <div class='border-b py-2'>
    <strong>{emoji}</strong> {comment or ''}
    <span class='text-sm text-gray-500'>– {user.username}</span>
  </div>
""")

@router.post("/{event_id}/feedback/{feedback_id}/pin", response_class=HTMLResponse)
async def toggle_pin_feedback(
    event_id: UUID,
    feedback_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if not event or event.host_id != user.id:
        raise HTTPException(status_code=403, detail="Only the host can toggle pin")

    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    feedback.pinned = not feedback.pinned
    await db.commit()

    return f"<div class='border-b py-2 flex justify-between items-center'><div><strong>{feedback.emoji}</strong> {feedback.comment or ''}</div><div>" + (
        f"<button hx-post='/events/{event_id}/feedback/{feedback.id}/pin' class='text-yellow-600 text-sm ml-2'>⭐ {'Unpin' if feedback.pinned else 'Pin'}</button>"
    ) + "</div></div>"


@router.post("/{event_id}/feedback/{feedback_id}/flag", response_class=HTMLResponse)
async def toggle_flag_feedback(
    event_id: UUID,
    feedback_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if not event or event.host_id != user.id:
        raise HTTPException(status_code=403, detail="Only the host can toggle flag")

    result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    feedback.flagged = not feedback.flagged
    await db.commit()

    return f"<div class='border-b py-2 flex justify-between items-center'><div><strong>{feedback.emoji}</strong> {feedback.comment or ''}</div><div>" + (
        f"<button hx-post='/events/{event_id}/feedback/{feedback.id}/flag' class='text-red-600 text-sm ml-2'>🚩 {'Unflag' if feedback.flagged else 'Flag'}</button>"
    ) + "</div></div>"
    

@router.get("/{event_id}/feedback/stream", response_class=HTMLResponse)
async def live_feedback_stream(
    request: Request,
    event_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    is_host = user.id == event.host_id

    result = await db.execute(
        select(Feedback).where(Feedback.event_id == event_id).order_by(Feedback.timestamp.desc()).limit(10)
    )
    feedbacks = result.scalars().all()

    rows = []
    for f in reversed(feedbacks):
        row = f"<div class='border-b py-2 flex justify-between items-center'><div><strong>{f.emoji}</strong> {f.comment or ''}</div>"
        if is_host:
            actions = []
            pin_label = "Unpin" if f.pinned else "Pin"
            flag_label = "Unflag" if f.flagged else "Flag"
            actions.append(f"<button hx-post='/events/{event_id}/feedback/{f.id}/pin' class='text-yellow-600 text-sm ml-2'>⭐ {pin_label}</button>")
            actions.append(f"<button hx-post='/events/{event_id}/feedback/{f.id}/flag' class='text-red-600 text-sm ml-2'>🚩 {flag_label}</button>")
            row += "<div>" + "".join(actions) + "</div>"
        row += "</div>"
        rows.append(row)

    return "".join(rows)

@router.get("/{event_id}/checkout")
async def checkout_event(
    request: Request,
    event_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if user.id == event.host_id and event.status != "Closed":
        event.status = "Closed"
        await db.commit()
        
    return templates.TemplateResponse("thank_you.html", {
        "request": request,
        "event": event
    })
    



@router.get("/{event_id}/summary")
async def event_summary(
    request: Request,
    event_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db)
):
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if not event or event.host_id != user.id:
        raise HTTPException(status_code=403, detail="Only the host can view the summary")

    # RSVP + Check-in counts
    rsvp_result = await db.execute(select(RSVP))
    rsvps = rsvp_result.scalars().all()
    rsvps = [r for r in rsvps if r.event_id == event_id]
    total_rsvps = len(rsvps)
    total_checkins = len([r for r in rsvps if r.check_in_time])

    # Feedback aggregation
    feedback_result = await db.execute(select(Feedback).where(Feedback.event_id == event_id))
    feedbacks = feedback_result.scalars().all()

    # Volume over time
    feedback_volume = collections.Counter(f.timestamp.strftime("%Y-%m-%d %H:%M") for f in feedbacks)
    feedback_volume_sorted = sorted(feedback_volume.items())

    # Top emojis
    emoji_counts = collections.Counter(f.emoji for f in feedbacks)
    top_emojis = emoji_counts.most_common(3)

    # Keyword extraction
    import re
    words = []
    for f in feedbacks:
        if f.comment:
            words += re.findall(r"\b[a-zA-Z]{4,}\b", f.comment.lower())

    # Get top 10 most common words, ignoring generic filler
    ignore = {"this", "that", "with", "have", "your", "about", "from", "what", "which"}
    filtered = [w for w in words if w not in ignore]
    common_keywords = [word for word, _ in Counter(filtered).most_common(10)]
    return templates.TemplateResponse("summary.html", {
        "request": request,
        "event": event,
        "total_rsvps": total_rsvps,
        "total_checkins": total_checkins,
        "feedback_volume": feedback_volume_sorted,
        "top_emojis": top_emojis,
        "keywords": common_keywords
    })


@router.get("/{event_id}")
async def view_event_detail(
    request: Request,
    event_id: UUID = Path(...),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.status == "Closed":
        return {"msg": "Event is closed"}
    
    current_utc_time = datetime.utcnow()  # Returns UTC datetime object
    today = current_utc_time.date() 
    event_date = event.datetime
    rsvp_open = current_utc_time < event.rsvp_deadline
    checkin_window_start = event.datetime - timedelta(hours=1)
    checkin_open = (
        current_utc_time >= checkin_window_start # Before event closes
    )
    return templates.TemplateResponse("event_detail.html", {
        "request": request,
        "event": event,
        "show_rsvp": rsvp_open,
        "show_checkin": checkin_open
    })

@router.get("/{event_id}/edit")
async def edit_event_form(
    request: Request,
    event_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if not event or event.host_id != user.id:
        raise HTTPException(status_code=403, detail="You are not authorized to edit this event")

    return templates.TemplateResponse("event_edit.html", {
        "request": request,
        "event": event
    })


@router.post("/{event_id}/edit")
async def update_event(
    request: Request,
    event_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
    title: str = Form(...),
    description: str = Form(""),
    datetime: datetime = Form(...),
    location: str = Form(...),
    rsvp_deadline: datetime = Form(...),
    max_attendees: int = Form(...),
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if not event or event.host_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    if rsvp_deadline >= datetime:
        return templates.TemplateResponse("event_edit.html", {
            "request": request,
            "event": event,
            "error": "RSVP deadline must be before event start time"
        })

    event.title = title
    event.description = description
    event.datetime = datetime
    event.location = location
    event.rsvp_deadline = rsvp_deadline
    event.max_attendees = max_attendees

    await db.commit()

    return RedirectResponse("/dashboard", status_code=302)

@router.post("/{event_id}/delete")
async def delete_event(
    event_id: UUID,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if not event or event.host_id != user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    await db.delete(event)
    await db.commit()

    return RedirectResponse("/dashboard", status_code=302)



@router.post("/{event_id}/rsvp")
async def rsvp_event(
    event_id: UUID,
    request: Request,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    today = datetime.utcnow().date()
    if today > event.rsvp_deadline.date():
        raise HTTPException(status_code=400, detail="RSVP deadline has passed")

    existing_rsvp = await db.execute(
        select(RSVP).where(RSVP.event_id == event_id, RSVP.user_id == user.id)
    )
    if existing_rsvp.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already RSVPed")

    rsvp = RSVP(event_id=event_id, user_id=user.id)
    db.add(rsvp)
    await db.commit()
    return {"msg":f"You're confirmed for '{event.title}' at {event.datetime.strftime('%Y-%m-%d %H:%M')} . Email Sent To: {user.email}"}

@router.post("/{event_id}/checkin")
async def checkin_event(
    event_id: UUID,
    request: Request,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(RSVP).where(RSVP.event_id == event_id, RSVP.user_id == user.id))
    rsvp = result.scalar_one_or_none()

    if not rsvp:
        raise HTTPException(status_code=404, detail="RSVP not found")

    today = datetime.utcnow().date()
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    
    current_utc_time = datetime.utcnow()  # Returns UTC datetime object
    checkin_window_start = event.datetime - timedelta(hours=1)
    checkin_open = (
        current_utc_time >= checkin_window_start # Before event closes
    )
    if checkin_open is False:
        raise HTTPException(status_code=400, detail="Check-in only allowed on event day")

    rsvp.check_in_time = datetime.utcnow()
    await db.commit()
    return RedirectResponse(url=f"/events/{event_id}/live", status_code=303)


@router.post("/{event_id}/walkin")
async def mark_walkin(
    request: Request,
    event_id: UUID,
    email: str = Form(...),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime
    from app.models.user import User as AppUser

    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()

    if not event or event.host_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Lookup user by email
    user_result = await db.execute(select(AppUser).where(AppUser.email == email))
    attendee = user_result.scalar_one_or_none()
    if not attendee:
        raise HTTPException(status_code=404, detail="No user found with that email")

    # Check if already RSVPed
    rsvp_result = await db.execute(select(RSVP).where(RSVP.user_id == attendee.id, RSVP.event_id == event_id))
    rsvp = rsvp_result.scalar_one_or_none()

    if not rsvp:
        # Create new RSVP with check-in
        new_rsvp = RSVP(user_id=attendee.id, event_id=event_id, check_in_time=datetime.utcnow())
        db.add(new_rsvp)
    elif not rsvp.check_in_time:
        # Just check in
        rsvp.check_in_time = datetime.utcnow()

    await db.commit()

    return RedirectResponse(f"/events/{event_id}/live", status_code=303)
