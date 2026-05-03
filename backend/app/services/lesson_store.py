from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.lesson import (
    LessonMessage,
    LessonSession,
    LessonSessionCreate,
    LessonSessionDetail,
    LessonSessionSummary,
    MessageRole,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class InMemoryLessonRepository:
    sessions: dict[str, LessonSession] = field(default_factory=dict)
    messages: dict[str, list[LessonMessage]] = field(default_factory=dict)

    def create_session(self, request: LessonSessionCreate) -> LessonSession:
        session = LessonSession(
            id=f"lesson-{uuid4().hex}",
            student_id=request.student_id,
            grade=request.grade,
            subject=request.subject,
            title=request.title,
            lesson_goal=request.lesson_goal,
            teacher_style=request.teacher_style,
            knowledge_points=request.knowledge_points,
            mode=request.mode,
        )
        self.sessions[session.id] = session
        self.messages[session.id] = [
            LessonMessage(
                id=f"msg-{uuid4().hex}",
                session_id=session.id,
                student_id=session.student_id,
                role="teacher",
                content=(
                    f"今天这节课的目标是：{session.lesson_goal}。"
                    "我会先问一个诊断问题，再根据你的回答安排讲解和练习。"
                ),
                phase=session.current_phase,
                message_type="lesson_opening",
            )
        ]
        return session

    def list_sessions(self, student_id: str) -> list[LessonSessionSummary]:
        sessions = [
            session for session in self.sessions.values() if session.student_id == student_id
        ]
        sessions.sort(key=lambda item: item.updated_at, reverse=True)
        return [
            LessonSessionSummary(
                id=session.id,
                title=session.title,
                subject=session.subject,
                grade=session.grade,
                status=session.status,
                current_phase=session.current_phase,
                pending_student_action=session.pending_student_action,
                summary=session.summary,
                updated_at=session.updated_at,
            )
            for session in sessions
        ]

    def get_session_detail(self, session_id: str) -> LessonSessionDetail | None:
        session = self.sessions.get(session_id)
        if session is None:
            return None
        return LessonSessionDetail(session=session, messages=self.messages.get(session_id, []))

    def append_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        message_type: str = "conversation",
    ) -> LessonMessage | None:
        session = self.sessions.get(session_id)
        if session is None:
            return None

        message = LessonMessage(
            id=f"msg-{uuid4().hex}",
            session_id=session.id,
            student_id=session.student_id,
            role=role,
            content=content,
            phase=session.current_phase,
            message_type=message_type,
        )
        self.messages.setdefault(session.id, []).append(message)

        session.updated_at = _now()
        if role == "teacher":
            session.pending_student_action = self._infer_pending_action(content)
            session.summary = self._summarize_session(session.id)
        self.sessions[session.id] = session
        return message

    def _infer_pending_action(self, teacher_reply: str) -> str:
        if "你先" in teacher_reply:
            return "完成老师刚刚要求的下一小步。"
        if "告诉我" in teacher_reply:
            return "回答老师提出的诊断问题。"
        return "继续回应老师的课堂引导。"

    def _summarize_session(self, session_id: str) -> str:
        messages = self.messages.get(session_id, [])
        student_turns = sum(1 for message in messages if message.role == "student")
        teacher_turns = sum(1 for message in messages if message.role == "teacher")
        return f"已进行 {teacher_turns} 轮教师引导和 {student_turns} 轮学生回应。"


_repository = InMemoryLessonRepository()


def get_lesson_repository() -> InMemoryLessonRepository:
    return _repository

