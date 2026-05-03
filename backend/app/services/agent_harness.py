import logging

from app.core.settings import settings
from app.schemas.teacher import MemoryEvent, TeacherChatRequest, TeacherChatResponse
from app.services.deepagents_runtime import DeepAgentsTeachingRuntime
from app.services.llm_provider import LlmProvider, MockTeacherProvider, TeacherPrompt, get_llm_provider
from app.services.lesson_store import LessonRepository, get_lesson_repository
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
        lesson_repository: LessonRepository,
        deepagents_runtime: DeepAgentsTeachingRuntime,
    ) -> None:
        self.memory_service = memory_service
        self.rag_service = rag_service
        self.skill_registry = skill_registry
        self.llm_provider = llm_provider
        self.lesson_repository = lesson_repository
        self.deepagents_runtime = deepagents_runtime

    def reply(self, request: TeacherChatRequest) -> TeacherChatResponse:
        effective_subject = self._infer_effective_subject(
            message=request.message,
            fallback_subject=request.context.subject,
        )

        if request.context.session_id:
            self.lesson_repository.append_message(
                session_id=request.context.session_id,
                role="student",
                content=request.message,
            )

        skills = self.skill_registry.pick_skills(request.context.grade, effective_subject)
        memory = self.memory_service.get_student_summary(request.context.student_id)
        retrieved_context = self.rag_service.retrieve(request.message)
        prompt = TeacherPrompt(
            message=request.message,
            grade=request.context.grade,
            subject=effective_subject,
            teacher_style=request.context.teacher_style,
            skill_name=f"{skills.core.name} + {skills.knowledge.name}",
            skill_guidance="\n\n".join(
                [
                    f"教师核心 Skill：\n{skills.core.guidance}",
                    f"知识点 Skill：\n{skills.knowledge.guidance}",
                ]
            ),
            memory_summary=memory,
            retrieved_context=retrieved_context,
            core_skill_name=skills.core.name,
            core_skill_guidance=skills.core.guidance,
            knowledge_skill_name=skills.knowledge.name,
            knowledge_skill_guidance=skills.knowledge.guidance,
        )
        reply = self._generate_reply(request, prompt)

        if request.context.session_id:
            self.lesson_repository.append_message(
                session_id=request.context.session_id,
                role="teacher",
                content=reply,
            )

        event = self.memory_service.record_learning_event(
            student_id=request.context.student_id,
            subject=effective_subject,
            message=request.message,
            reply=reply,
        )

        return TeacherChatResponse(
            reply=reply,
            skill_id=skills.response_skill_id,
            memory_events=[MemoryEvent(kind=event.kind, summary=event.summary)],
        )

    def _generate_reply(self, request: TeacherChatRequest, prompt: TeacherPrompt) -> str:
        if settings.agent_runtime == "deepagents":
            try:
                return self.deepagents_runtime.generate_reply(request, prompt).reply
            except Exception:
                logger.exception("DeepAgents runtime failed; falling back to LLM provider")

        try:
            return self.llm_provider.generate_reply(prompt)
        except Exception:
            logger.exception("LLM provider failed; falling back to mock teacher provider")
            return MockTeacherProvider().generate_reply(prompt)

    def _infer_effective_subject(self, message: str, fallback_subject: str) -> str:
        normalized = message.lower()
        if any(keyword in normalized for keyword in ["浮力", "受力", "重力", "斜面", "物理"]):
            return "物理"
        if any(keyword in normalized for keyword in ["英语", "单词", "语法", "yesterday", "verb", "go "]):
            return "英语"
        if any(keyword in normalized for keyword in ["语文", "作文", "阅读", "比喻", "修辞"]):
            return "语文"
        return fallback_subject


def get_agent_harness() -> AgentHarness:
    lesson_repository = get_lesson_repository()
    memory_service = get_memory_service()
    return AgentHarness(
        memory_service=memory_service,
        rag_service=get_rag_service(),
        skill_registry=get_skill_registry(),
        llm_provider=get_llm_provider(),
        lesson_repository=lesson_repository,
        deepagents_runtime=DeepAgentsTeachingRuntime(
            memory_service=memory_service,
            lesson_repository=lesson_repository,
        ),
    )
