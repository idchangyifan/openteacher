from app.schemas.teacher import MemoryEvent, TeacherChatRequest, TeacherChatResponse
from app.services.memory import MemoryService, get_memory_service
from app.services.rag import RagService, get_rag_service
from app.services.skill_registry import SkillRegistry, get_skill_registry


class AgentHarness:
    def __init__(
        self,
        memory_service: MemoryService,
        rag_service: RagService,
        skill_registry: SkillRegistry,
    ) -> None:
        self.memory_service = memory_service
        self.rag_service = rag_service
        self.skill_registry = skill_registry

    def reply(self, request: TeacherChatRequest) -> TeacherChatResponse:
        skill = self.skill_registry.pick_skill(request.context.grade, request.context.subject)
        memory = self.memory_service.get_student_summary(request.context.student_id)
        retrieved_context = self.rag_service.retrieve(request.message)

        reply = self._mock_teacher_reply(
            message=request.message,
            grade=request.context.grade,
            subject=request.context.subject,
            skill_name=skill.name,
            memory_summary=memory,
            retrieved_context=retrieved_context,
        )

        event = self.memory_service.record_learning_event(
            student_id=request.context.student_id,
            subject=request.context.subject,
            message=request.message,
            reply=reply,
        )

        return TeacherChatResponse(
            reply=reply,
            skill_id=skill.id,
            memory_events=[MemoryEvent(kind=event.kind, summary=event.summary)],
        )

    def _mock_teacher_reply(
        self,
        message: str,
        grade: str,
        subject: str,
        skill_name: str,
        memory_summary: str,
        retrieved_context: str,
    ) -> str:
        normalized = message.strip()

        if any(word in normalized for word in ["答案", "直接告诉", "抄"]):
            return (
                "不行。我是老师，不是答案机器。你先写出下一步，我会检查你的推理。"
                "如果你写错，我会指出具体错在哪里。"
            )

        if "x" in normalized or "(" in normalized or "（" in normalized:
            return (
                f"我会按「{skill_name}」来教。先停在第一步，不要跳答案。"
                "请你写出去括号后的式子，并说明每一项的符号为什么这样变。"
                f"我记得你的学习重点是：{memory_summary}。"
            )

        if any(word in normalized for word in ["笨", "学不会", "不会", "太难"]):
            return (
                "先别给自己下结论。我们按老师的方式处理：你告诉我卡在读题、列式、"
                "去括号、移项、合并同类项，还是验算？只回答一个也可以。"
            )

        return (
            f"收到。当前是{grade}{subject}场景。请补充题目原文和你已经写到的步骤。"
            f"我会结合{retrieved_context}来判断你的卡点。"
        )


def get_agent_harness() -> AgentHarness:
    return AgentHarness(
        memory_service=get_memory_service(),
        rag_service=get_rag_service(),
        skill_registry=get_skill_registry(),
    )
