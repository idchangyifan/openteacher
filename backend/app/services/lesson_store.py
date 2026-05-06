from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Protocol
from uuid import uuid4

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument

from app.core.settings import settings
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


class LessonRepository(Protocol):
    def create_session(self, request: LessonSessionCreate) -> LessonSession: ...

    def list_sessions(self, student_id: str) -> list[LessonSessionSummary]: ...

    def get_session_detail(self, session_id: str) -> LessonSessionDetail | None: ...

    def append_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        message_type: str = "conversation",
    ) -> LessonMessage | None: ...

    def update_session_state(
        self,
        session_id: str,
        *,
        current_skill_id: str | None = None,
        current_knowledge_point_id: str | None = None,
        current_chapter_id: str | None = None,
        current_section_id: str | None = None,
    ) -> LessonSession | None: ...


class LessonRepositoryMixin:
    def _opening_message(self, session: LessonSession) -> LessonMessage:
        return LessonMessage(
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

    def _infer_pending_action(self, teacher_reply: str) -> str:
        if "你先" in teacher_reply:
            return "完成老师刚刚要求的下一小步。"
        if "告诉我" in teacher_reply:
            return "回答老师提出的诊断问题。"
        return "继续回应老师的课堂引导。"

    def _summarize_messages(self, messages: list[LessonMessage]) -> str:
        student_turns = sum(1 for message in messages if message.role == "student")
        teacher_turns = sum(1 for message in messages if message.role == "teacher")
        return f"已进行 {teacher_turns} 轮教师引导和 {student_turns} 轮学生回应。"


@dataclass
class InMemoryLessonRepository(LessonRepositoryMixin):
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
        self.messages[session.id] = [self._opening_message(session)]
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
                current_chapter_id=session.current_chapter_id,
                current_section_id=session.current_section_id,
                current_knowledge_point_id=session.current_knowledge_point_id,
                current_skill_id=session.current_skill_id,
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
            session.summary = self._summarize_messages(self.messages.get(session.id, []))
        self.sessions[session.id] = session
        return message

    def update_session_state(
        self,
        session_id: str,
        *,
        current_skill_id: str | None = None,
        current_knowledge_point_id: str | None = None,
        current_chapter_id: str | None = None,
        current_section_id: str | None = None,
    ) -> LessonSession | None:
        session = self.sessions.get(session_id)
        if session is None:
            return None

        session.current_skill_id = current_skill_id
        session.current_knowledge_point_id = current_knowledge_point_id
        session.current_chapter_id = current_chapter_id
        session.current_section_id = current_section_id
        session.updated_at = _now()
        self.sessions[session.id] = session
        return session


class MongoLessonRepository(LessonRepositoryMixin):
    def __init__(
        self,
        uri: str,
        database: str,
        client: MongoClient | None = None,
    ) -> None:
        self.client = client or MongoClient(uri, serverSelectionTimeoutMS=3000)
        self.db = self.client[database]
        self.sessions = self.db["lesson_sessions"]
        self.messages = self.db["lesson_messages"]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.sessions.create_index(
            [("student_id", ASCENDING), ("updated_at", DESCENDING)],
            name="student_updated",
        )
        self.sessions.create_index(
            [("student_id", ASCENDING), ("subject", ASCENDING), ("updated_at", DESCENDING)],
            name="student_subject_updated",
        )
        self.sessions.create_index(
            [("status", ASCENDING), ("updated_at", DESCENDING)],
            name="status_updated",
        )
        self.messages.create_index(
            [("session_id", ASCENDING), ("created_at", ASCENDING)],
            name="session_created",
        )
        self.messages.create_index(
            [("student_id", ASCENDING), ("created_at", DESCENDING)],
            name="student_created",
        )

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
        self.sessions.insert_one(self._session_to_document(session))
        self.messages.insert_one(self._message_to_document(self._opening_message(session)))
        return session

    def list_sessions(self, student_id: str) -> list[LessonSessionSummary]:
        documents = self.sessions.find({"student_id": student_id}).sort("updated_at", DESCENDING)
        return [
            LessonSessionSummary(
                id=document["_id"],
                title=document["title"],
                subject=document["subject"],
                grade=document["grade"],
                status=document["status"],
                current_phase=document["current_phase"],
                current_chapter_id=document.get("current_chapter_id"),
                current_section_id=document.get("current_section_id"),
                current_knowledge_point_id=document.get("current_knowledge_point_id"),
                current_skill_id=document.get("current_skill_id"),
                pending_student_action=document["pending_student_action"],
                summary=document["summary"],
                updated_at=document["updated_at"],
            )
            for document in documents
        ]

    def get_session_detail(self, session_id: str) -> LessonSessionDetail | None:
        session_document = self.sessions.find_one({"_id": session_id})
        if session_document is None:
            return None

        message_documents = self.messages.find({"session_id": session_id}).sort(
            "created_at", ASCENDING
        )
        return LessonSessionDetail(
            session=self._session_from_document(session_document),
            messages=[self._message_from_document(document) for document in message_documents],
        )

    def append_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        message_type: str = "conversation",
    ) -> LessonMessage | None:
        session = self.sessions.find_one({"_id": session_id})
        if session is None:
            return None

        message = LessonMessage(
            id=f"msg-{uuid4().hex}",
            session_id=session_id,
            student_id=session["student_id"],
            role=role,
            content=content,
            phase=session["current_phase"],
            message_type=message_type,
        )
        self.messages.insert_one(self._message_to_document(message))

        update: dict[str, object] = {"updated_at": _now()}
        if role == "teacher":
            documents = self.messages.find({"session_id": session_id})
            messages = [self._message_from_document(document) for document in documents]
            update["pending_student_action"] = self._infer_pending_action(content)
            update["summary"] = self._summarize_messages(messages)
        self.sessions.update_one({"_id": session_id}, {"$set": update})
        return message

    def update_session_state(
        self,
        session_id: str,
        *,
        current_skill_id: str | None = None,
        current_knowledge_point_id: str | None = None,
        current_chapter_id: str | None = None,
        current_section_id: str | None = None,
    ) -> LessonSession | None:
        update = {
            "current_skill_id": current_skill_id,
            "current_knowledge_point_id": current_knowledge_point_id,
            "current_chapter_id": current_chapter_id,
            "current_section_id": current_section_id,
            "updated_at": _now(),
        }
        result = self.sessions.find_one_and_update(
            {"_id": session_id},
            {"$set": update},
            return_document=ReturnDocument.AFTER,
        )
        if result is None:
            return None
        return self._session_from_document(result)

    def _session_to_document(self, session: LessonSession) -> dict:
        document = session.model_dump()
        document["_id"] = document.pop("id")
        return document

    def _session_from_document(self, document: dict) -> LessonSession:
        payload = dict(document)
        payload["id"] = payload.pop("_id")
        return LessonSession(**payload)

    def _message_to_document(self, message: LessonMessage) -> dict:
        document = message.model_dump()
        document["_id"] = document.pop("id")
        return document

    def _message_from_document(self, document: dict) -> LessonMessage:
        payload = dict(document)
        payload["id"] = payload.pop("_id")
        return LessonMessage(**payload)


_memory_repository = InMemoryLessonRepository()


@lru_cache
def get_mongo_lesson_repository() -> MongoLessonRepository:
    return MongoLessonRepository(uri=settings.mongodb_uri, database=settings.mongodb_database)


def get_lesson_repository() -> LessonRepository:
    if settings.lesson_store_backend == "mongodb":
        return get_mongo_lesson_repository()
    return _memory_repository
