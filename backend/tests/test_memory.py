from app.services.memory import MemoryCard, MemoryExtractionJob, MemoryService


class CapturingMemoryService(MemoryService):
    def __init__(self) -> None:
        self.cards: list[MemoryCard] = []
        self.jobs: list[MemoryExtractionJob] = []

    def retrieve_memory_cards(
        self,
        student_id: str,
        subject: str = "",
        limit: int = 5,
    ) -> list[MemoryCard]:
        return [
            card
            for card in self.cards
            if card.student_id == student_id and (not subject or card.subject == subject)
        ][:limit]

    def upsert_memory_card(self, card: MemoryCard) -> MemoryCard:
        self.cards = [item for item in self.cards if item.id != card.id]
        self.cards.insert(0, card)
        return card

    def record_extraction_job(self, job: MemoryExtractionJob) -> MemoryExtractionJob:
        self.jobs.append(job)
        return job

    def mark_source_session_deleted(self, session_id: str) -> None:
        self.cards = [
            MemoryCard(
                **{
                    **card.__dict__,
                    "source_session_deleted": True,
                }
            )
            if card.source_session_id == session_id
            else card
            for card in self.cards
        ]


def test_memory_service_extracts_positive_negative_memory_card() -> None:
    service = CapturingMemoryService()

    event = service.record_learning_event(
        student_id="memory-card-student",
        subject="数学",
        message="-6",
        reply="对啦。收入10元记作+10，支出6元要用负数表示。",
        source_session_id="lesson-positive-negative",
        source_message_ids=["msg-student", "msg-teacher"],
    )

    assert event.kind == "academic_signal"
    assert event.summary == "学生正在学习正数和负数"
    assert service.cards[0].summary == "学生正在学习正数和负数"
    assert "正数" in service.cards[0].tags
    assert "负数" in service.cards[0].tags
    assert service.cards[0].source_session_id == "lesson-positive-negative"
    assert service.cards[0].source_message_ids == ["msg-student", "msg-teacher"]
    assert service.cards[0].review_status == "auto_accepted"
    assert service.cards[0].evidence_snippets == [
        "student: -6",
        "teacher: 对啦。收入10元记作+10，支出6元要用负数表示。",
    ]
    assert service.jobs[0].source_session_id == "lesson-positive-negative"
    assert service.jobs[0].card_ids == [service.cards[0].id]


def test_deleted_lesson_source_marks_memory_without_removing_card() -> None:
    service = CapturingMemoryService()
    service.record_learning_event(
        student_id="memory-card-student",
        subject="数学",
        message="-6",
        reply="支出6元记作-6。",
        source_session_id="lesson-to-delete",
    )

    service.mark_source_session_deleted("lesson-to-delete")

    assert len(service.cards) == 1
    assert service.cards[0].summary == "学生正在学习正数和负数"
    assert service.cards[0].source_session_deleted is True


def test_deepagents_memory_snapshot_includes_memory_cards_as_background() -> None:
    service = CapturingMemoryService()
    service.upsert_memory_card(
        MemoryCard(
            id="memory-card-positive-negative",
            student_id="memory-card-student",
            subject="数学",
            kind="academic_signal",
            summary="学生正在学习正数和负数",
            evidence="student: -6",
            confidence=0.72,
            tags=["正数", "负数"],
        )
    )

    memory_text = service.format_deepagents_memory(
        student_id="memory-card-student",
        subject="数学",
    )

    assert "OpenTeacher Student Memory" in memory_text
    assert "学生正在学习正数和负数" in memory_text
    assert "Long-term memory is background only" in memory_text
    assert "never override current_skill_id" in memory_text
