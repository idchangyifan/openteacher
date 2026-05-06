from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LessonMode = Literal["active_lesson", "qa"]
LessonStatus = Literal["in_progress", "completed", "archived"]
LessonPhase = Literal[
    "lesson_start",
    "concept_instruction",
    "diagnostic_check",
    "guided_practice",
    "adaptive_remediation",
    "lesson_summary",
    "homework_assignment",
]
MessageRole = Literal["teacher", "student", "system"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LessonSessionCreate(BaseModel):
    student_id: str = "demo-student"
    grade: str = "初一"
    subject: str = "数学"
    title: str = "今日课堂"
    lesson_goal: str = "先诊断当前水平，再完成一个小练习"
    teacher_style: str = "严格但温暖"
    knowledge_points: list[str] = Field(default_factory=list)
    mode: LessonMode = "active_lesson"

    model_config = ConfigDict(str_strip_whitespace=True)


class LessonSession(BaseModel):
    id: str
    student_id: str
    grade: str
    subject: str
    title: str
    lesson_goal: str
    teacher_style: str
    knowledge_points: list[str] = Field(default_factory=list)
    mode: LessonMode = "active_lesson"
    status: LessonStatus = "in_progress"
    current_phase: LessonPhase = "lesson_start"
    current_chapter_id: str | None = None
    current_section_id: str | None = None
    current_knowledge_point_id: str | None = None
    current_skill_id: str | None = None
    pending_student_action: str = "回答老师的第一个诊断问题"
    summary: str = "课堂刚开始，尚未形成复习摘要。"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class LessonMessage(BaseModel):
    id: str
    session_id: str
    student_id: str
    role: MessageRole
    content: str
    phase: LessonPhase = "lesson_start"
    message_type: str = "conversation"
    created_at: datetime = Field(default_factory=utc_now)


class LessonSessionSummary(BaseModel):
    id: str
    title: str
    subject: str
    grade: str
    status: LessonStatus
    current_phase: LessonPhase
    current_chapter_id: str | None = None
    current_section_id: str | None = None
    current_knowledge_point_id: str | None = None
    current_skill_id: str | None = None
    pending_student_action: str
    summary: str
    updated_at: datetime


class LessonSessionDetail(BaseModel):
    session: LessonSession
    messages: list[LessonMessage]
