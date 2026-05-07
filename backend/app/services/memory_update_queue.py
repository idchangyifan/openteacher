from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
import threading
import time
from uuid import uuid4

from pymongo import ASCENDING, MongoClient, ReturnDocument

from app.core.settings import settings
from app.services.memory import LearningEvent, MemoryService, get_memory_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MemoryUpdateTask:
    id: str
    student_id: str
    subject: str
    message: str
    reply: str
    source_session_id: str | None = None
    source_message_ids: list[str] = field(default_factory=list)
    status: str = "pending"
    attempts: int = 0
    error: str | None = None
    event_kind: str | None = None
    event_summary: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class MemoryUpdateSubmission:
    task_id: str
    status: str
    event: LearningEvent | None = None


class MemoryUpdateQueue:
    def enqueue(self, task: MemoryUpdateTask) -> MemoryUpdateTask:
        return task

    def claim_pending(self, limit: int = 10) -> list[MemoryUpdateTask]:
        return []

    def mark_completed(self, task_id: str, event: LearningEvent) -> None:
        return None

    def mark_failed(self, task_id: str, error: str, attempts: int) -> None:
        return None


class InMemoryMemoryUpdateQueue(MemoryUpdateQueue):
    def __init__(self) -> None:
        self.tasks: list[MemoryUpdateTask] = []

    def enqueue(self, task: MemoryUpdateTask) -> MemoryUpdateTask:
        self.tasks.append(task)
        return task

    def claim_pending(self, limit: int = 10) -> list[MemoryUpdateTask]:
        claimed: list[MemoryUpdateTask] = []
        next_tasks: list[MemoryUpdateTask] = []
        for task in self.tasks:
            if task.status == "pending" and len(claimed) < limit:
                claimed.append(
                    MemoryUpdateTask(
                        **{
                            **task.__dict__,
                            "status": "processing",
                            "attempts": task.attempts + 1,
                        }
                    )
                )
            else:
                next_tasks.append(task)
        self.tasks = next_tasks + claimed
        return claimed

    def mark_completed(self, task_id: str, event: LearningEvent) -> None:
        self.tasks = [
            MemoryUpdateTask(
                **{
                    **task.__dict__,
                    "status": "completed",
                    "event_kind": event.kind,
                    "event_summary": event.summary,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            if task.id == task_id
            else task
            for task in self.tasks
        ]

    def mark_failed(self, task_id: str, error: str, attempts: int) -> None:
        self.tasks = [
            MemoryUpdateTask(
                **{
                    **task.__dict__,
                    "status": "failed",
                    "error": error,
                    "attempts": attempts,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            if task.id == task_id
            else task
            for task in self.tasks
        ]


class MongoMemoryUpdateQueue(MemoryUpdateQueue):
    def __init__(
        self,
        uri: str,
        database: str,
        client: MongoClient | None = None,
    ) -> None:
        self.client = client or MongoClient(uri, serverSelectionTimeoutMS=3000)
        self.collection = self.client[database]["memory_update_tasks"]
        self.collection.create_index(
            [("status", ASCENDING), ("created_at", ASCENDING)],
            name="status_created",
        )
        self.collection.create_index(
            [("source_session_id", ASCENDING), ("created_at", ASCENDING)],
            name="source_session_created",
        )

    def enqueue(self, task: MemoryUpdateTask) -> MemoryUpdateTask:
        document = self._task_to_document(task)
        self.collection.insert_one(document)
        return task

    def claim_pending(self, limit: int = 10) -> list[MemoryUpdateTask]:
        claimed: list[MemoryUpdateTask] = []
        now = datetime.now(timezone.utc)
        for _ in range(limit):
            document = self.collection.find_one_and_update(
                {
                    "status": "pending",
                    "attempts": {"$lt": settings.memory_update_worker_max_attempts},
                    "$or": [
                        {"next_attempt_at": {"$exists": False}},
                        {"next_attempt_at": {"$lte": now}},
                    ],
                },
                {
                    "$set": {"status": "processing", "locked_at": now, "updated_at": now},
                    "$inc": {"attempts": 1},
                },
                sort=[("created_at", ASCENDING)],
                return_document=ReturnDocument.AFTER,
            )
            if document is None:
                break
            claimed.append(self._task_from_document(document))
        return claimed

    def mark_completed(self, task_id: str, event: LearningEvent) -> None:
        now = datetime.now(timezone.utc)
        self.collection.update_one(
            {"_id": task_id},
            {
                "$set": {
                    "status": "completed",
                    "event_kind": event.kind,
                    "event_summary": event.summary,
                    "event_learning_status": event.learning_status,
                    "event_topic_key": event.topic_key,
                    "completed_at": now,
                    "updated_at": now,
                }
            },
        )

    def mark_failed(self, task_id: str, error: str, attempts: int) -> None:
        now = datetime.now(timezone.utc)
        next_status = (
            "dead_letter"
            if attempts >= settings.memory_update_worker_max_attempts
            else "pending"
        )
        self.collection.update_one(
            {"_id": task_id},
            {
                "$set": {
                    "status": next_status,
                    "error": error,
                    "next_attempt_at": now + timedelta(seconds=min(30, 2**attempts)),
                    "updated_at": now,
                }
            },
        )

    def _task_to_document(self, task: MemoryUpdateTask) -> dict:
        return {
            "_id": task.id,
            "student_id": task.student_id,
            "subject": task.subject,
            "message": task.message,
            "reply": task.reply,
            "source_session_id": task.source_session_id,
            "source_message_ids": task.source_message_ids,
            "status": task.status,
            "attempts": task.attempts,
            "error": task.error,
            "event_kind": task.event_kind,
            "event_summary": task.event_summary,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    def _task_from_document(self, document: dict) -> MemoryUpdateTask:
        return MemoryUpdateTask(
            id=str(document["_id"]),
            student_id=str(document["student_id"]),
            subject=str(document.get("subject") or ""),
            message=str(document.get("message") or ""),
            reply=str(document.get("reply") or ""),
            source_session_id=document.get("source_session_id"),
            source_message_ids=[
                str(value) for value in document.get("source_message_ids", []) or []
            ],
            status=str(document.get("status") or "pending"),
            attempts=int(document.get("attempts") or 0),
            error=document.get("error"),
            event_kind=document.get("event_kind"),
            event_summary=document.get("event_summary"),
            created_at=document.get("created_at") or datetime.now(timezone.utc),
            updated_at=document.get("updated_at") or datetime.now(timezone.utc),
        )


class MemoryUpdateDispatcher:
    def __init__(
        self,
        memory_service: MemoryService,
        queue: MemoryUpdateQueue | None = None,
        inline: bool = True,
    ) -> None:
        self.memory_service = memory_service
        self.queue = queue or MemoryUpdateQueue()
        self.inline = inline

    def submit(
        self,
        *,
        student_id: str,
        subject: str,
        message: str,
        reply: str,
        source_session_id: str | None = None,
        source_message_ids: list[str] | None = None,
    ) -> MemoryUpdateSubmission:
        task = MemoryUpdateTask(
            id=f"memory-update-task-{uuid4().hex}",
            student_id=student_id,
            subject=subject,
            message=message,
            reply=reply,
            source_session_id=source_session_id,
            source_message_ids=source_message_ids or [],
        )
        if self.inline:
            event = self.memory_service.record_learning_event(
                student_id=student_id,
                subject=subject,
                message=message,
                reply=reply,
                source_session_id=source_session_id,
                source_message_ids=source_message_ids or [],
            )
            return MemoryUpdateSubmission(task_id=task.id, status="completed", event=event)

        self.queue.enqueue(task)
        return MemoryUpdateSubmission(task_id=task.id, status="queued")


class MemoryUpdateWorker:
    def __init__(self, queue: MemoryUpdateQueue, memory_service: MemoryService) -> None:
        self.queue = queue
        self.memory_service = memory_service
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def process_once(self) -> int:
        processed = 0
        tasks = self.queue.claim_pending(limit=settings.memory_update_worker_batch_size)
        for task in tasks:
            try:
                event = self.memory_service.record_learning_event(
                    student_id=task.student_id,
                    subject=task.subject,
                    message=task.message,
                    reply=task.reply,
                    source_session_id=task.source_session_id,
                    source_message_ids=task.source_message_ids,
                )
                self.queue.mark_completed(task.id, event)
                processed += 1
            except Exception as exc:
                logger.exception("Memory update task failed: %s", task.id)
                self.queue.mark_failed(task.id, str(exc), task.attempts)
        return processed

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.process_once()
            time.sleep(settings.memory_update_worker_poll_seconds)


def build_memory_update_queue() -> MemoryUpdateQueue:
    backend = settings.memory_update_queue_backend.strip().lower()
    if backend == "mongodb":
        return MongoMemoryUpdateQueue(settings.mongodb_uri, settings.mongodb_database)
    if backend == "memory":
        return InMemoryMemoryUpdateQueue()
    return MemoryUpdateQueue()


def build_memory_update_dispatcher(
    memory_service: MemoryService,
) -> MemoryUpdateDispatcher:
    backend = settings.memory_update_queue_backend.strip().lower()
    if backend in {"mongodb", "memory"}:
        return MemoryUpdateDispatcher(
            memory_service=memory_service,
            queue=build_memory_update_queue(),
            inline=False,
        )
    return MemoryUpdateDispatcher(memory_service=memory_service, inline=True)


def start_memory_update_worker() -> MemoryUpdateWorker | None:
    backend = settings.memory_update_queue_backend.strip().lower()
    if backend not in {"mongodb", "memory"}:
        return None
    worker = MemoryUpdateWorker(build_memory_update_queue(), get_memory_service())
    worker.start()
    return worker
