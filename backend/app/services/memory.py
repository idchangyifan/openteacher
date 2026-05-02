from dataclasses import dataclass


@dataclass(frozen=True)
class LearningEvent:
    kind: str
    summary: str


class MemoryService:
    """Boundary for student memory storage.

    The first version is intentionally in-memory/mock-like. Later this can point to
    PostgreSQL, pgvector, a vector database, or a hybrid memory store.
    """

    def get_student_summary(self, student_id: str) -> str:
        return "移项符号容易错，需要分步骤检查"

    def record_learning_event(
        self,
        student_id: str,
        subject: str,
        message: str,
        reply: str,
    ) -> LearningEvent:
        if any(word in message for word in ["答案", "直接告诉", "抄"]):
            return LearningEvent(kind="learning_behavior", summary="学生尝试直接获取答案")

        if "x" in message:
            return LearningEvent(kind="academic_signal", summary="学生正在练习一元一次方程")

        return LearningEvent(kind="conversation", summary=f"学生进行了{subject}学习对话")


def get_memory_service() -> MemoryService:
    return MemoryService()
