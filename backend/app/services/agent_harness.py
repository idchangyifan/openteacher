import logging

from app.schemas.teacher import MemoryEvent, TeacherChatRequest, TeacherChatResponse
from app.services.llm_provider import LlmProvider, MockTeacherProvider, TeacherPrompt, get_llm_provider
from app.services.memory import MemoryService, get_memory_service
from app.services.rag import RagService, get_rag_service
from app.services.skill_registry import SkillRegistry, get_skill_registry

logger = logging.getLogger(__name__)


class AgentHarness:
    def __init__(
        self,
        memory_service: MemoryService,
        rag_service: RagService,
        skill_registry: SkillRegistry,
        llm_provider: LlmProvider,
    ) -> None:
        self.memory_service = memory_service
        self.rag_service = rag_service
        self.skill_registry = skill_registry
        self.llm_provider = llm_provider

    def reply(self, request: TeacherChatRequest) -> TeacherChatResponse:
        skill = self.skill_registry.pick_skill(request.context.grade, request.context.subject)
        memory = self.memory_service.get_student_summary(request.context.student_id)
        retrieved_context = self.rag_service.retrieve(request.message)
        prompt = TeacherPrompt(
            message=request.message,
            grade=request.context.grade,
            subject=request.context.subject,
            teacher_style=request.context.teacher_style,
            skill_name=skill.name,
            memory_summary=memory,
            retrieved_context=retrieved_context,
        )
        reply = self._generate_reply(prompt)

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

    def _generate_reply(self, prompt: TeacherPrompt) -> str:
        try:
            return self.llm_provider.generate_reply(prompt)
        except Exception:
            logger.exception("LLM provider failed; falling back to mock teacher provider")
            return MockTeacherProvider().generate_reply(prompt)


def get_agent_harness() -> AgentHarness:
    return AgentHarness(
        memory_service=get_memory_service(),
        rag_service=get_rag_service(),
        skill_registry=get_skill_registry(),
        llm_provider=get_llm_provider(),
    )
