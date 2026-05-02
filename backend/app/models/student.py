from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    preferred_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    school_stage: Mapped[str] = mapped_column(String(20), default="junior")
    grade: Mapped[str] = mapped_column(String(20), default="初一")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
