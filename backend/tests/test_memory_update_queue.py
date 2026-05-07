from app.services.memory import MemoryService
from app.services.memory_update_queue import (
    InMemoryMemoryUpdateQueue,
    MemoryUpdateDispatcher,
    MemoryUpdateTask,
    MemoryUpdateWorker,
)


class CapturingMemoryService(MemoryService):
    def __init__(self) -> None:
        self.recorded: list[tuple[str, str, str, str]] = []

    def record_learning_event(
        self,
        student_id: str,
        subject: str,
        message: str,
        reply: str,
        source_session_id: str | None = None,
        source_message_ids: list[str] | None = None,
    ):
        self.recorded.append((student_id, subject, message, reply))
        return super().record_learning_event(
            student_id=student_id,
            subject=subject,
            message=message,
            reply=reply,
            source_session_id=source_session_id,
            source_message_ids=source_message_ids,
        )


def test_queued_memory_update_dispatcher_does_not_extract_inline() -> None:
    memory_service = CapturingMemoryService()
    queue = InMemoryMemoryUpdateQueue()
    dispatcher = MemoryUpdateDispatcher(memory_service, queue=queue, inline=False)

    submission = dispatcher.submit(
        student_id="async-memory-student",
        subject="数学",
        message="因为支出和收入是相反意义的量，收入用+表示，所以支出用-表示",
        reply="完全正确。",
        source_session_id="lesson-1",
        source_message_ids=["student-message", "teacher-message"],
    )

    assert submission.status == "queued"
    assert submission.event is None
    assert len(memory_service.recorded) == 0
    assert queue.tasks[0].status == "pending"
    assert queue.tasks[0].source_message_ids == ["student-message", "teacher-message"]


def test_memory_update_worker_consumes_queued_task() -> None:
    memory_service = CapturingMemoryService()
    queue = InMemoryMemoryUpdateQueue()
    queue.enqueue(
        MemoryUpdateTask(
            id="memory-update-task-test",
            student_id="async-memory-student",
            subject="数学",
            message="因为支出和收入是相反意义的量，收入用+表示，所以支出用-表示",
            reply="完全正确。",
        )
    )
    worker = MemoryUpdateWorker(queue, memory_service)

    processed = worker.process_once()

    assert processed == 1
    assert len(memory_service.recorded) == 1
    assert queue.tasks[0].status == "completed"
    assert queue.tasks[0].event_summary == "学生能够解释正数和负数表示相反意义的量"
