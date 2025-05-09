# 🎉 EventPulse – Real-Time Event Engagement Platform

EventPulse is a event management platform built using **FastAPI**. It allows hosts to create events, track attendance, collect live feedback, and view post-event insights all in one place.

---

## 🚀 Features


### 🛠 For Hosts (any user that creats an event is the host for that event)
- Create & manage events (with location, RSVP deadline, attendee cap)
- Real-time check-in tracking and walk-in support
- Live feedback stream with pin/flag moderation
- Analytics summary with charts and keyword cloud
- Event editing & deletion
- Dashboard and calendar views

### 🙋 For Attendees
- RSVP to events and check in on event day
- Submit live feedback with emoji reactions
- Join events from calendar interface

---

## 🧑‍💻 Tech Stack

- **Backend**: FastAPI, SQLAlchemy, Alembic, PostgreSQL
- **Frontend**: Jinja2 templates, TailwindCSS, HTMX
- **Auth**: FastAPI Users (JWT + Cookie)
- **Database**: PostgreSQL (async with `asyncpg`)
- **Extras**: Chart.js for feedback analytics, custom middleware, mock email notifications

---

## 📦 How to Run Locally

> **Requires Python 3.11+**

```bash
# Clone the repo
git clone https://github.com/yourname/eventpulse.git
cd eventpulse

# Create and activate Conda env (Python 3.11)
conda create -n eventpulse python=3.11
conda activate eventpulse

# Install dependencies
pip install -r app/requirements.txt


# Run server
uvicorn app.main:app --reload
