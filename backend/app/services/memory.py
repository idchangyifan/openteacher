from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
from typing import TYPE_CHECKING
from uuid import uuid4

from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument

from app.core.settings import settings

if TYPE_CHECKING:
    from app.schemas.lesson import LessonSessionDetail, LessonSessionSummary


@dataclass(frozen=True)
class LearningEvent:
    kind: str
    summary: str


@dataclass(frozen=True)
class MemoryCard:
    id: str
    student_id: str
    subject: str
    kind: str
    summary: str
    evidence: str
    confidence: float
    status: str = "active"
    tags: list[str] = field(default_factory=list)
    source: str = "controlled_extraction"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MemoryService:
    """Boundary for student memory storage.

    The first version is intentionally in-memory/mock-like. Long-term memory should
    move behind this boundary into MongoDB-backed lesson history, structured memory
    cards, extraction jobs, and vector search. Do not bind student long-term memory
    to PostgreSQL tables.
    """

    def get_student_summary(
        self,
        student_id: str,
        subject: str = "",
        lesson_detail: "LessonSessionDetail | None" = None,
        recent_lessons: "list[LessonSessionSummary] | None" = None,
    ) -> str:
        memory_cards = self.retrieve_memory_cards(student_id, subject=subject)
        return self.format_student_summary(
            student_id=student_id,
            subject=subject,
            lesson_detail=lesson_detail,
            recent_lessons=recent_lessons,
            memory_cards=memory_cards,
        )

    def format_student_summary(
        self,
        *,
        student_id: str,
        subject: str = "",
        lesson_detail: "LessonSessionDetail | None" = None,
        recent_lessons: "list[LessonSessionSummary] | None" = None,
        memory_cards: list[MemoryCard] | None = None,
    ) -> str:
        memory_parts: list[str] = []
        if lesson_detail is not None:
            session = lesson_detail.session
            memory_parts.extend(
                [
                    "当前课堂优先",
                    f"课堂：{session.title}",
                    f"目标：{session.lesson_goal}",
                    f"科目：{session.grade}{session.subject}",
                    f"当前 skill：{session.current_skill_id or '未设置'}",
                    f"当前知识点：{session.current_knowledge_point_id or '未设置'}",
                    f"课堂摘要：{session.summary}",
                ]
            )
            last_teacher_message = next(
                (
                    message.content
                    for message in reversed(lesson_detail.messages)
                    if message.role == "teacher"
                ),
                "",
            )
            if last_teacher_message:
                memory_parts.append(f"最近老师引导：{last_teacher_message}")

        if recent_lessons:
            formatted_recent_lessons = []
            current_session_id = (
                lesson_detail.session.id if lesson_detail is not None else None
            )
            for lesson in recent_lessons[:3]:
                if lesson.id == current_session_id:
                    continue
                formatted_recent_lessons.append(
                    (
                        f"{lesson.grade}{lesson.subject}《{lesson.title}》"
                        f" skill={lesson.current_skill_id or '未设置'}"
                        f" 知识点={lesson.current_knowledge_point_id or '未设置'}"
                        f" 摘要={lesson.summary}"
                    )
                )
            if formatted_recent_lessons:
                memory_parts.append("最近课堂：" + " | ".join(formatted_recent_lessons))

        if memory_cards:
            formatted_cards = [
                f"{card.kind}:{card.summary} (confidence={card.confidence:.2f})"
                for card in memory_cards[:5]
            ]
            memory_parts.append("长期记忆卡片（背景假设）：" + " | ".join(formatted_cards))

        if memory_parts:
            memory_parts.append("优先级：当前课堂记录 > 当前课堂状态 > 最近课堂 > 长期背景假设。")
            return "；".join(memory_parts)

        subject_note = f"{subject}学习" if subject else "当前学习"
        return f"暂无可靠长期记忆；优先依据当前课堂记录和学生本轮输入来判断{subject_note}。"

    def format_deepagents_memory(
        self,
        *,
        student_id: str,
        subject: str,
        lesson_detail: "LessonSessionDetail | None" = None,
        recent_lessons: "list[LessonSessionSummary] | None" = None,
    ) -> str:
        summary = self.get_student_summary(
            student_id,
            subject=subject,
            lesson_detail=lesson_detail,
            recent_lessons=recent_lessons,
        )
        return "\n".join(
            [
                "# OpenTeacher Student Memory",
                "",
                f"student_id: {student_id}",
                f"subject: {subject or 'unknown'}",
                "",
                "## Memory Priority",
                "",
                "- Current lesson transcript and lesson state are authoritative.",
                "- Long-term memory is background only; never override current_skill_id.",
                "- If current and long-term memory conflict, trust the current lesson.",
                "",
                "## Memory Summary",
                "",
                summary,
            ]
        )

    def record_learning_event(
        self,
        student_id: str,
        subject: str,
        message: str,
        reply: str,
    ) -> LearningEvent:
        event = self._extract_learning_event(subject=subject, message=message, reply=reply)
        card = self._memory_card_from_event(
            student_id=student_id,
            subject=subject,
            event=event,
            message=message,
            reply=reply,
        )
        if card is not None:
            self.upsert_memory_card(card)
        return event

    def retrieve_memory_cards(
        self,
        student_id: str,
        subject: str = "",
        limit: int = 5,
    ) -> list[MemoryCard]:
        return []

    def upsert_memory_card(self, card: MemoryCard) -> MemoryCard:
        return card

    def _extract_learning_event(self, subject: str, message: str, reply: str) -> LearningEvent:
        if any(word in message for word in ["答案", "直接告诉", "抄"]):
            return LearningEvent(kind="learning_behavior", summary="学生尝试直接获取答案")

        if any(token in f"{message}\n{reply}" for token in ["正数", "负数", "收入", "支出", "+10", "-6"]):
            return LearningEvent(kind="academic_signal", summary="学生正在学习正数和负数")

        if "x" in message:
            return LearningEvent(kind="academic_signal", summary="学生正在练习一元一次方程")

        return LearningEvent(kind="conversation", summary=f"学生进行了{subject}学习对话")

    def _memory_card_from_event(
        self,
        *,
        student_id: str,
        subject: str,
        event: LearningEvent,
        message: str,
        reply: str,
    ) -> MemoryCard | None:
        if event.kind == "conversation":
            return None
        return MemoryCard(
            id=self._stable_card_id(student_id, subject, event.kind, event.summary),
            student_id=student_id,
            subject=subject,
            kind=event.kind,
            summary=event.summary,
            evidence=f"student: {message}\nteacher: {reply}",
            confidence=0.72 if event.kind == "academic_signal" else 0.82,
            tags=self._memory_tags(event.summary),
        )

    def _stable_card_id(self, student_id: str, subject: str, kind: str, summary: str) -> str:
        raw = f"{student_id}:{subject}:{kind}:{summary}"
        if not raw.strip(":"):
            return f"memory-{uuid4().hex}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
        return f"memory-{digest}"

    def _memory_tags(self, summary: str) -> list[str]:
        tags = []
        for token in ["正数", "负数", "一元一次方程", "直接获取答案"]:
            if token in summary:
                tags.append(token)
        return tags


class MongoMemoryService(MemoryService):
    def __init__(
        self,
        uri: str,
        database: str,
        client: MongoClient | None = None,
    ) -> None:
        self.client = client or MongoClient(uri, serverSelectionTimeoutMS=3000)
        self.db = self.client[database]
        self.cards = self.db["memory_cards"]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.cards.create_index(
            [("student_id", ASCENDING), ("subject", ASCENDING), ("updated_at", DESCENDING)],
            name="student_subject_updated",
        )
        self.cards.create_index(
            [("student_id", ASCENDING), ("status", ASCENDING)],
            name="student_status",
        )
        self.cards.create_index([("kind", ASCENDING), ("tags", ASCENDING)], name="kind_tags")

    def retrieve_memory_cards(
        self,
        student_id: str,
        subject: str = "",
        limit: int = 5,
    ) -> list[MemoryCard]:
        query: dict[str, object] = {"student_id": student_id, "status": "active"}
        if subject:
            query["subject"] = subject
        documents = self.cards.find(query).sort("updated_at", DESCENDING).limit(limit)
        return [self._card_from_document(document) for document in documents]

    def upsert_memory_card(self, card: MemoryCard) -> MemoryCard:
        now = datetime.now(timezone.utc)
        payload = self._card_to_document(card)
        payload["updated_at"] = now
        payload.setdefault("created_at", card.created_at)
        result = self.cards.find_one_and_update(
            {"_id": card.id},
            {
                "$set": {
                    "summary": card.summary,
                    "evidence": card.evidence,
                    "confidence": card.confidence,
                    "status": card.status,
                    "tags": card.tags,
                    "source": card.source,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "student_id": card.student_id,
                    "subject": card.subject,
                    "kind": card.kind,
                    "created_at": card.created_at,
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return self._card_from_document(result or payload)

    def _card_to_document(self, card: MemoryCard) -> dict:
        document = {
            "_id": card.id,
            "student_id": card.student_id,
            "subject": card.subject,
            "kind": card.kind,
            "summary": card.summary,
            "evidence": card.evidence,
            "confidence": card.confidence,
            "status": card.status,
            "tags": card.tags,
            "source": card.source,
            "created_at": card.created_at,
            "updated_at": card.updated_at,
        }
        return document

    def _card_from_document(self, document: dict) -> MemoryCard:
        return MemoryCard(
            id=str(document["_id"]),
            student_id=str(document["student_id"]),
            subject=str(document.get("subject") or ""),
            kind=str(document["kind"]),
            summary=str(document["summary"]),
            evidence=str(document.get("evidence") or ""),
            confidence=float(document.get("confidence") or 0.0),
            status=str(document.get("status") or "active"),
            tags=[str(value) for value in document.get("tags", []) or []],
            source=str(document.get("source") or "controlled_extraction"),
            created_at=document.get("created_at") or datetime.now(timezone.utc),
            updated_at=document.get("updated_at") or datetime.now(timezone.utc),
        )


@lru_cache
def get_mongo_memory_service() -> MongoMemoryService:
    return MongoMemoryService(uri=settings.mongodb_uri, database=settings.mongodb_database)


def get_memory_service() -> MemoryService:
    if settings.memory_backend == "mongodb":
        return get_mongo_memory_service()
    return MemoryService()
