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
        previous = next((item for item in self.cards if item.id == card.id), None)
        learning_status = self._resolve_learning_status(
            previous.learning_status if previous else None,
            card.learning_status,
        )
        if previous and self._should_preserve_existing_memory_fact(
            previous.learning_status,
            card.learning_status,
            learning_status,
        ):
            stored = MemoryCard(
                **{
                    **card.__dict__,
                    "kind": previous.kind,
                    "summary": previous.summary,
                    "confidence": previous.confidence,
                    "tags": previous.tags,
                    "learning_status": learning_status,
                }
            )
        else:
            stored = MemoryCard(**{**card.__dict__, "learning_status": learning_status})
        self.cards = [item for item in self.cards if item.id != card.id]
        self.cards.insert(0, stored)
        return stored

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
    assert service.cards[0].learning_status == "in_progress"
    assert service.cards[0].topic_key == "kp-positive-negative-numbers"
    assert service.cards[0].evidence_snippets == [
        "student: -6",
        "teacher: 对啦。收入10元记作+10，支出6元要用负数表示。",
    ]
    assert service.jobs[0].source_session_id == "lesson-positive-negative"
    assert service.jobs[0].card_ids == [service.cards[0].id]
    assert service.jobs[0].event_learning_status == "in_progress"
    assert service.jobs[0].event_topic_key == "kp-positive-negative-numbers"


def test_memory_service_updates_positive_negative_card_to_needs_placement() -> None:
    service = CapturingMemoryService()
    service.record_learning_event(
        student_id="memory-card-student",
        subject="数学",
        message="-6",
        reply="支出6元记作-6。",
        source_session_id="lesson-positive-negative",
    )
    first_card_id = service.cards[0].id

    event = service.record_learning_event(
        student_id="memory-card-student",
        subject="数学",
        message="不是应该先教负数吗？",
        reply="你问得对，我先确认你是没学过还是学过但没懂。",
        source_session_id="lesson-positive-negative",
    )

    assert event.kind == "course_placement"
    assert event.learning_status == "needs_placement"
    assert len(service.cards) == 1
    assert service.cards[0].id == first_card_id
    assert service.cards[0].summary == "学生需要确认正数和负数的学习起点"
    assert service.cards[0].learning_status == "needs_placement"


def test_memory_service_only_marks_mastery_when_student_gives_reasoning() -> None:
    service = CapturingMemoryService()
    service.record_learning_event(
        student_id="memory-card-student",
        subject="数学",
        message="-6",
        reply="对啦，但还要说出为什么。",
        source_session_id="lesson-positive-negative",
    )
    first_card_id = service.cards[0].id

    event = service.record_learning_event(
        student_id="memory-card-student",
        subject="数学",
        message="因为支出和收入相反，所以支出6元记作-6。",
        reply="这个解释是对的。",
        source_session_id="lesson-positive-negative",
    )

    assert event.learning_status == "mastered"
    assert len(service.cards) == 1
    assert service.cards[0].id == first_card_id
    assert service.cards[0].learning_status == "mastered"
    assert service.cards[0].summary == "学生能够解释正数和负数表示相反意义的量"


def test_memory_service_marks_mastery_when_student_explains_sign_without_number() -> None:
    service = CapturingMemoryService()

    event = service.record_learning_event(
        student_id="memory-card-student",
        subject="数学",
        message="因为支出和收入是相反意义的量，收入用+表示，所以支出用-表示",
        reply="完全正确。",
        source_session_id="lesson-positive-negative",
    )

    assert event.learning_status == "mastered"
    assert service.cards[0].learning_status == "mastered"
    assert service.cards[0].summary == "学生能够解释正数和负数表示相反意义的量"


def test_memory_service_does_not_downgrade_mastery_on_later_topic_mention() -> None:
    service = CapturingMemoryService()
    service.record_learning_event(
        student_id="memory-card-student",
        subject="数学",
        message="因为支出和收入相反，所以支出6元记作-6。",
        reply="这个解释是对的。",
        source_session_id="lesson-positive-negative",
    )

    service.record_learning_event(
        student_id="memory-card-student",
        subject="数学",
        message="继续讲正数和负数",
        reply="好，我们继续。",
        source_session_id="lesson-positive-negative",
    )

    assert len(service.cards) == 1
    assert service.cards[0].learning_status == "mastered"
    assert service.cards[0].summary == "学生能够解释正数和负数表示相反意义的量"


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
    assert "learning_status=in_progress" in memory_text
    assert "topic=unknown" in memory_text
    assert "Long-term memory is background only" in memory_text
    assert "never override current_skill_id" in memory_text
