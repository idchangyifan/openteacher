from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LearningEvent(Base):
    __tablename__ = "learning_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("students.id"), index=True)
    subject: Mapped[str] = mapped_column(String(40), default="数学")
    kind: Mapped[str] = mapped_column(String(60))
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
