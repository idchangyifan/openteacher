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
    learning_status: str = "in_progress"
    topic_key: str | None = None
    confidence: float = 0.72


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
    source_session_id: str | None = None
    source_message_ids: list[str] = field(default_factory=list)
    evidence_snippets: list[str] = field(default_factory=list)
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    review_status: str = "auto_accepted"
    learning_status: str = "in_progress"
    topic_key: str | None = None
    expires_at: datetime | None = None
    supersedes: list[str] = field(default_factory=list)
    conflict_group: str | None = None
    source_session_deleted: bool = False
    source_session_deleted_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class MemoryExtractionJob:
    id: str
    student_id: str
    subject: str
    status: str
    event_kind: str
    event_summary: str
    event_learning_status: str = "in_progress"
    event_topic_key: str | None = None
    source_session_id: str | None = None
    source_message_ids: list[str] = field(default_factory=list)
    card_ids: list[str] = field(default_factory=list)
    error: str | None = None
    extractor_version: str = "controlled-v1"
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
                (
                    f"{card.kind}:{card.summary} "
                    f"(learning_status={card.learning_status}; "
                    f"topic={card.topic_key or 'unknown'}; "
                    f"confidence={card.confidence:.2f}; "
                    "学习信号不等于已经掌握)"
                )
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
                "- A memory card saying the student is learning a topic is not mastery.",
                (
                    "- learning_status=needs_placement means ask what the student "
                    "has already learned before moving on."
                ),
                (
                    "- learning_status=needs_support means slow down and diagnose "
                    "the stuck point."
                ),
                (
                    "- learning_status=in_progress means continue teaching, not "
                    "that the student mastered it."
                ),
                (
                    "- learning_status=mastered needs student reasoning evidence, "
                    "not a bare final answer."
                ),
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
        source_session_id: str | None = None,
        source_message_ids: list[str] | None = None,
    ) -> LearningEvent:
        event = self._extract_learning_event(subject=subject, message=message, reply=reply)
        source_message_ids = source_message_ids or []
        card = self._memory_card_from_event(
            student_id=student_id,
            subject=subject,
            event=event,
            message=message,
            reply=reply,
            source_session_id=source_session_id,
            source_message_ids=source_message_ids,
        )
        card_ids = []
        if card is not None:
            stored_card = self.upsert_memory_card(card)
            card_ids.append(stored_card.id)
        job = MemoryExtractionJob(
            id=f"memory-job-{uuid4().hex}",
            student_id=student_id,
            subject=subject,
            status="completed",
            event_kind=event.kind,
            event_summary=event.summary,
            event_learning_status=event.learning_status,
            event_topic_key=event.topic_key,
            source_session_id=source_session_id,
            source_message_ids=source_message_ids,
            card_ids=card_ids,
        )
        self.record_extraction_job(job)
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

    def record_extraction_job(self, job: MemoryExtractionJob) -> MemoryExtractionJob:
        return job

    def mark_source_session_deleted(self, session_id: str) -> None:
        return None

    def _extract_learning_event(self, subject: str, message: str, reply: str) -> LearningEvent:
        if any(word in message for word in ["答案", "直接告诉", "抄"]):
            return LearningEvent(
                kind="learning_behavior",
                summary="学生尝试直接获取答案",
                learning_status="needs_support",
                confidence=0.82,
            )

        if self._looks_like_lesson_memory_question(message):
            return LearningEvent(kind="conversation", summary=f"学生询问{subject}课堂进度")

        if self._looks_like_positive_negative_placement_question(message):
            return LearningEvent(
                kind="course_placement",
                summary="学生需要确认正数和负数的学习起点",
                learning_status="needs_placement",
                topic_key="kp-positive-negative-numbers",
                confidence=0.86,
            )

        if any(
            token in f"{message}\n{reply}"
            for token in ["正数", "负数", "收入", "支出", "+10", "-6"]
        ):
            if self._looks_like_positive_negative_mastery(message):
                return LearningEvent(
                    kind="academic_signal",
                    summary="学生能够解释正数和负数表示相反意义的量",
                    learning_status="mastered",
                    topic_key="kp-positive-negative-numbers",
                    confidence=0.84,
                )
            if self._looks_like_student_stuck(message):
                return LearningEvent(
                    kind="academic_signal",
                    summary="学生在正数和负数上需要支持",
                    learning_status="needs_support",
                    topic_key="kp-positive-negative-numbers",
                    confidence=0.78,
                )
            return LearningEvent(
                kind="academic_signal",
                summary="学生正在学习正数和负数",
                learning_status="in_progress",
                topic_key="kp-positive-negative-numbers",
                confidence=0.72,
            )

        if "x" in message:
            return LearningEvent(
                kind="academic_signal",
                summary="学生正在练习一元一次方程",
                topic_key="kp-linear-equation",
            )

        return LearningEvent(kind="conversation", summary=f"学生进行了{subject}学习对话")

    def _memory_card_from_event(
        self,
        *,
        student_id: str,
        subject: str,
        event: LearningEvent,
        message: str,
        reply: str,
        source_session_id: str | None = None,
        source_message_ids: list[str] | None = None,
    ) -> MemoryCard | None:
        if event.kind == "conversation":
            return None
        evidence_snippets = [f"student: {message}", f"teacher: {reply}"]
        return MemoryCard(
            id=self._stable_card_id(
                student_id,
                subject,
                event.kind,
                event.summary,
                topic_key=event.topic_key,
            ),
            student_id=student_id,
            subject=subject,
            kind=event.kind,
            summary=event.summary,
            evidence=f"student: {message}\nteacher: {reply}",
            confidence=event.confidence,
            tags=self._memory_tags(event.summary),
            source_session_id=source_session_id,
            source_message_ids=source_message_ids or [],
            evidence_snippets=evidence_snippets,
            learning_status=event.learning_status,
            topic_key=event.topic_key,
            conflict_group=self._memory_conflict_group(event.summary),
        )

    def _stable_card_id(
        self,
        student_id: str,
        subject: str,
        kind: str,
        summary: str,
        topic_key: str | None = None,
    ) -> str:
        raw = (
            f"{student_id}:{subject}:topic:{topic_key}"
            if topic_key
            else f"{student_id}:{subject}:{kind}:{summary}"
        )
        if not raw.strip(":"):
            return f"memory-{uuid4().hex}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
        return f"memory-{digest}"

    def _memory_tags(self, summary: str) -> list[str]:
        tags = []
        for token in ["正数", "负数", "一元一次方程", "直接获取答案", "学习起点"]:
            if token in summary:
                tags.append(token)
        return tags

    def _memory_conflict_group(self, summary: str) -> str | None:
        if "正数" in summary or "负数" in summary:
            return "current_math_topic"
        if "一元一次方程" in summary:
            return "current_math_topic"
        return None

    def _looks_like_positive_negative_placement_question(self, message: str) -> bool:
        if "负数" not in message:
            return False
        return any(
            token in message
            for token in ["先教", "先学", "先讲", "不先", "应该先", "为什么", "顺序", "开始"]
        )

    def _looks_like_positive_negative_mastery(self, message: str) -> bool:
        compact = message.replace(" ", "")
        has_signed_quantity = any(
            token in compact
            for token in ["-6", "负六", "用-", "用负", "负数", "负号", "记作-"]
        )
        has_opposite_meaning = "收入" in message and "支出" in message and "相反" in message
        if not has_signed_quantity and not has_opposite_meaning:
            return False
        return any(
            token in message
            for token in [
                "因为",
                "所以",
                "支出",
                "花",
                "少",
                "减少",
                "相反",
                "负数",
                "记作",
                "亏",
                "下降",
                "低于",
            ]
        )

    def _looks_like_student_stuck(self, message: str) -> bool:
        return any(token in message for token in ["不知道", "不懂", "不会", "没学过", "看不懂", "听不懂"])

    def _looks_like_lesson_memory_question(self, message: str) -> bool:
        return any(
            token in message
            for token in [
                "上堂课",
                "上节课",
                "上一节",
                "上次",
                "刚才讲",
                "讲到哪",
                "讲到哪里",
                "讲了什么",
                "学了什么",
                "学到哪",
                "学到哪里",
                "记得我学",
                "你知道我学",
                "我学到哪",
                "我学到哪里",
            ]
        )

    def _resolve_learning_status(
        self,
        previous_status: str | None,
        incoming_status: str,
    ) -> str:
        if incoming_status in {"needs_placement", "needs_support", "mastered"}:
            return incoming_status
        if previous_status in {"needs_placement", "needs_support", "mastered"}:
            return previous_status
        return incoming_status

    def _should_preserve_existing_memory_fact(
        self,
        previous_status: str | None,
        incoming_status: str,
        resolved_status: str,
    ) -> bool:
        return (
            incoming_status == "in_progress"
            and previous_status in {"needs_placement", "needs_support", "mastered"}
            and resolved_status != incoming_status
        )


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
        self.extraction_jobs = self.db["memory_extraction_jobs"]
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
        self.cards.create_index(
            [("source_session_id", ASCENDING), ("updated_at", DESCENDING)],
            name="source_session_updated",
        )
        self.cards.create_index(
            [("review_status", ASCENDING), ("updated_at", DESCENDING)],
            name="review_status_updated",
        )
        self.cards.create_index(
            [("student_id", ASCENDING), ("subject", ASCENDING), ("topic_key", ASCENDING)],
            name="student_subject_topic",
        )
        self.extraction_jobs.create_index(
            [("student_id", ASCENDING), ("created_at", DESCENDING)],
            name="student_created",
        )
        self.extraction_jobs.create_index(
            [("source_session_id", ASCENDING), ("created_at", DESCENDING)],
            name="source_session_created",
        )
        self.extraction_jobs.create_index(
            [("status", ASCENDING), ("created_at", DESCENDING)],
            name="status_created",
        )

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
        existing_document = self.cards.find_one({"_id": card.id})
        previous_status = (
            str(existing_document.get("learning_status") or "in_progress")
            if existing_document
            else None
        )
        learning_status = self._resolve_learning_status(previous_status, card.learning_status)
        preserve_existing_fact = bool(
            existing_document
            and self._should_preserve_existing_memory_fact(
                previous_status,
                card.learning_status,
                learning_status,
            )
        )
        summary = (
            str(existing_document.get("summary") or card.summary)
            if preserve_existing_fact
            else card.summary
        )
        kind = (
            str(existing_document.get("kind") or card.kind)
            if preserve_existing_fact
            else card.kind
        )
        confidence = (
            float(existing_document.get("confidence") or card.confidence)
            if preserve_existing_fact
            else card.confidence
        )
        tags = (
            [str(value) for value in existing_document.get("tags", []) or []]
            if preserve_existing_fact
            else card.tags
        )
        payload = self._card_to_document(card)
        payload["updated_at"] = now
        payload["learning_status"] = learning_status
        payload["summary"] = summary
        payload["kind"] = kind
        payload["confidence"] = confidence
        payload["tags"] = tags
        payload.setdefault("created_at", card.created_at)
        result = self.cards.find_one_and_update(
            {"_id": card.id},
            {
                "$set": {
                    "kind": kind,
                    "summary": summary,
                    "evidence": card.evidence,
                    "confidence": confidence,
                    "status": card.status,
                    "tags": tags,
                    "source": card.source,
                    "source_session_id": card.source_session_id,
                    "source_message_ids": card.source_message_ids,
                    "evidence_snippets": card.evidence_snippets,
                    "last_seen_at": now,
                    "review_status": card.review_status,
                    "learning_status": learning_status,
                    "topic_key": card.topic_key,
                    "expires_at": card.expires_at,
                    "supersedes": card.supersedes,
                    "conflict_group": card.conflict_group,
                    "source_session_deleted": card.source_session_deleted,
                    "source_session_deleted_at": card.source_session_deleted_at,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "student_id": card.student_id,
                    "subject": card.subject,
                    "created_at": card.created_at,
                },
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return self._card_from_document(result or payload)

    def record_extraction_job(self, job: MemoryExtractionJob) -> MemoryExtractionJob:
        self.extraction_jobs.insert_one(self._job_to_document(job))
        return job

    def mark_source_session_deleted(self, session_id: str) -> None:
        now = datetime.now(timezone.utc)
        self.cards.update_many(
            {"source_session_id": session_id},
            {
                "$set": {
                    "source_session_deleted": True,
                    "source_session_deleted_at": now,
                    "updated_at": now,
                }
            },
        )
        self.extraction_jobs.update_many(
            {"source_session_id": session_id},
            {
                "$set": {
                    "source_session_deleted": True,
                    "source_session_deleted_at": now,
                    "updated_at": now,
                }
            },
        )

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
            "source_session_id": card.source_session_id,
            "source_message_ids": card.source_message_ids,
            "evidence_snippets": card.evidence_snippets,
            "last_seen_at": card.last_seen_at,
            "review_status": card.review_status,
            "learning_status": card.learning_status,
            "topic_key": card.topic_key,
            "expires_at": card.expires_at,
            "supersedes": card.supersedes,
            "conflict_group": card.conflict_group,
            "source_session_deleted": card.source_session_deleted,
            "source_session_deleted_at": card.source_session_deleted_at,
            "created_at": card.created_at,
            "updated_at": card.updated_at,
        }
        return document

    def _job_to_document(self, job: MemoryExtractionJob) -> dict:
        document = {
            "_id": job.id,
            "student_id": job.student_id,
            "subject": job.subject,
            "status": job.status,
            "event_kind": job.event_kind,
            "event_summary": job.event_summary,
            "event_learning_status": job.event_learning_status,
            "event_topic_key": job.event_topic_key,
            "source_session_id": job.source_session_id,
            "source_message_ids": job.source_message_ids,
            "card_ids": job.card_ids,
            "error": job.error,
            "extractor_version": job.extractor_version,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
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
            source_session_id=document.get("source_session_id"),
            source_message_ids=[
                str(value) for value in document.get("source_message_ids", []) or []
            ],
            evidence_snippets=[
                str(value) for value in document.get("evidence_snippets", []) or []
            ],
            last_seen_at=document.get("last_seen_at") or datetime.now(timezone.utc),
            review_status=str(document.get("review_status") or "auto_accepted"),
            learning_status=str(document.get("learning_status") or "in_progress"),
            topic_key=document.get("topic_key"),
            expires_at=document.get("expires_at"),
            supersedes=[str(value) for value in document.get("supersedes", []) or []],
            conflict_group=document.get("conflict_group"),
            source_session_deleted=bool(document.get("source_session_deleted") or False),
            source_session_deleted_at=document.get("source_session_deleted_at"),
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
