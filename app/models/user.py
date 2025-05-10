from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String
import uuid
from app.db.base import Base 


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "user"

    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=True)
