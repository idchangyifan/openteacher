from app.services.memory import MemoryCard, MemoryService


class CapturingMemoryService(MemoryService):
    def __init__(self) -> None:
        self.cards: list[MemoryCard] = []

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


def test_memory_service_extracts_positive_negative_memory_card() -> None:
    service = CapturingMemoryService()

    event = service.record_learning_event(
        student_id="memory-card-student",
        subject="数学",
        message="-6",
        reply="对啦。收入10元记作+10，支出6元要用负数表示。",
    )

    assert event.kind == "academic_signal"
    assert event.summary == "学生正在学习正数和负数"
    assert service.cards[0].summary == "学生正在学习正数和负数"
    assert "正数" in service.cards[0].tags
    assert "负数" in service.cards[0].tags


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
