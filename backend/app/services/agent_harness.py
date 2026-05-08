import logging

from app.core.settings import settings
from app.schemas.lesson import LessonSessionDetail
from app.schemas.teacher import MemoryEvent, TeacherChatRequest, TeacherChatResponse
from app.services.deepagents_runtime import DeepAgentsTeachingRuntime
from app.services.llm_provider import LlmProvider, MockTeacherProvider, TeacherPrompt, get_llm_provider
from app.services.lesson_store import LessonRepository, get_lesson_repository
from app.services.memory import MemoryService, get_memory_service
from app.services.memory_update_queue import (
    MemoryUpdateDispatcher,
    build_memory_update_dispatcher,
)
from app.services.planner import PlannerService, get_planner_service
from app.services.rag import RagService, RagTurnContext, get_rag_service
from app.services.skill_registry import SkillRegistry, TeachingSkill, get_skill_registry
from app.services.teaching_turn_context import (
    evaluate_student_answer,
    format_message_lines,
    infer_current_question,
)

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
        planner_service: PlannerService,
        memory_update_dispatcher: MemoryUpdateDispatcher | None = None,
    ) -> None:
        self.memory_service = memory_service
        self.rag_service = rag_service
        self.skill_registry = skill_registry
        self.llm_provider = llm_provider
        self.lesson_repository = lesson_repository
        self.deepagents_runtime = deepagents_runtime
        self.planner_service = planner_service
        self.memory_update_dispatcher = memory_update_dispatcher or build_memory_update_dispatcher(
            memory_service
        )

    def reply(self, request: TeacherChatRequest) -> TeacherChatResponse:
        effective_subject = self._infer_effective_subject(
            message=request.message,
            fallback_subject=request.context.subject,
        )
        request = self._attach_recent_lesson_for_continuation(request, effective_subject)

        student_message_id = None
        if request.context.session_id:
            student_message = self.lesson_repository.append_message(
                session_id=request.context.session_id,
                role="student",
                content=request.message,
            )
            student_message_id = student_message.id if student_message is not None else None

        lesson_detail = (
            self.lesson_repository.get_session_detail(request.context.session_id)
            if request.context.session_id
            else None
        )
        current_skill_id = (
            lesson_detail.session.current_skill_id if lesson_detail is not None else None
        ) or self._recent_continuity_skill_id(
            student_id=request.context.student_id,
            subject=effective_subject,
            grade=request.context.grade,
            current_session_id=request.context.session_id,
            message=request.message,
        )
        skills = self.skill_registry.pick_skills(
            request.context.grade,
            effective_subject,
            message=request.message,
            current_skill_id=current_skill_id,
        )
        if request.context.session_id:
            self.lesson_repository.update_session_state(
                request.context.session_id,
                **self._lesson_state_from_skill(skills.knowledge, lesson_detail),
            )
            lesson_detail = self.lesson_repository.get_session_detail(request.context.session_id)

        rag_query = self._build_lesson_context_query(request.message, lesson_detail)
        memory = self.memory_service.get_student_summary(
            request.context.student_id,
            subject=effective_subject,
            lesson_detail=lesson_detail,
            recent_lessons=self._recent_lesson_summaries(
                request.context.student_id,
                effective_subject,
                request.context.grade,
            ),
        )
        planner_decision = self.planner_service.plan(
            request,
            effective_subject=effective_subject,
            skills=skills,
            memory_summary=memory,
            lesson_detail=lesson_detail,
        )
        current_question = infer_current_question(lesson_detail.messages if lesson_detail else [])
        answer_evaluation = evaluate_student_answer(current_question, request.message)
        rag_context = self._build_rag_turn_context(
            query=rag_query,
            message=request.message,
            lesson_detail=lesson_detail,
            teaching_mode=planner_decision.teaching_mode,
            learner_state=planner_decision.learner_state,
            next_teacher_goal=planner_decision.next_teacher_goal,
            current_question=current_question,
            student_answer_status=answer_evaluation.status,
        )
        retrieved_context = self.rag_service.retrieve_for_turn(rag_context)
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
            planner_context=planner_decision.to_prompt_context(),
        )
        reply = self._generate_reply(request, prompt)

        teacher_message_id = None
        if request.context.session_id:
            teacher_message = self.lesson_repository.append_message(
                session_id=request.context.session_id,
                role="teacher",
                content=reply,
            )
            teacher_message_id = teacher_message.id if teacher_message is not None else None

        submission = self.memory_update_dispatcher.submit(
            student_id=request.context.student_id,
            subject=effective_subject,
            message=request.message,
            reply=reply,
            source_session_id=request.context.session_id,
            source_message_ids=[
                message_id
                for message_id in [student_message_id, teacher_message_id]
                if message_id is not None
            ],
        )
        memory_events = (
            [MemoryEvent(kind=submission.event.kind, summary=submission.event.summary)]
            if submission.event is not None
            else [MemoryEvent(kind="memory_update_queued", summary="学习进度更新已排队")]
        )

        return TeacherChatResponse(
            reply=reply,
            skill_id=skills.response_skill_id,
            memory_events=memory_events,
        )

    def _attach_recent_lesson_for_continuation(
        self,
        request: TeacherChatRequest,
        effective_subject: str,
    ) -> TeacherChatRequest:
        if request.context.session_id or not self._looks_like_lesson_continuation(request.message):
            return request

        sessions = self.lesson_repository.list_sessions(request.context.student_id)
        candidates = [
            session
            for session in sessions
            if session.subject == effective_subject and session.grade == request.context.grade
        ]
        if not candidates:
            candidates = [
                session for session in sessions if session.subject == effective_subject
            ]
        if not candidates:
            return request

        next_context = request.context.model_copy(update={"session_id": candidates[0].id})
        return request.model_copy(update={"context": next_context})

    def _recent_continuity_skill_id(
        self,
        *,
        student_id: str,
        subject: str,
        grade: str,
        current_session_id: str | None,
        message: str,
    ) -> str | None:
        if not self._looks_like_lesson_continuation(message):
            return None

        sessions = [
            session
            for session in self.lesson_repository.list_sessions(student_id)
            if session.id != current_session_id
            and session.subject == subject
            and session.grade == grade
            and session.current_skill_id
        ]
        if not sessions:
            sessions = [
                session
                for session in self.lesson_repository.list_sessions(student_id)
                if session.id != current_session_id
                and session.subject == subject
                and session.current_skill_id
            ]
        return sessions[0].current_skill_id if sessions else None

    def _recent_lesson_summaries(
        self,
        student_id: str,
        subject: str,
        grade: str,
    ):
        return [
            session
            for session in self.lesson_repository.list_sessions(student_id)
            if session.subject == subject and session.grade == grade
        ][:3]

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

    def _looks_like_lesson_continuation(self, message: str) -> bool:
        return any(
            token in message
            for token in [
                "上堂课",
                "上节课",
                "上一节",
                "上次",
                "刚才",
                "继续",
                "讲到哪",
                "讲到哪里",
                "讲了什么",
                "学了什么",
                "复习一下",
                "接着",
            ]
        )

    def _build_lesson_context_query(
        self,
        message: str,
        lesson_detail: LessonSessionDetail | None,
    ) -> str:
        if lesson_detail is None:
            return message

        if not lesson_detail.messages:
            return message

        history = "\n".join(format_message_lines(lesson_detail.messages))
        state_lines = [
            f"current_chapter_id={lesson_detail.session.current_chapter_id or ''}",
            f"current_section_id={lesson_detail.session.current_section_id or ''}",
            f"current_knowledge_point_id={lesson_detail.session.current_knowledge_point_id or ''}",
            f"current_skill_id={lesson_detail.session.current_skill_id or ''}",
        ]
        return f"{message}\n\n当前课堂状态：\n" + "\n".join(state_lines) + f"\n\n完整课堂记录：\n{history}"

    def _build_rag_turn_context(
        self,
        *,
        query: str,
        message: str,
        lesson_detail: LessonSessionDetail | None,
        teaching_mode: str,
        learner_state: str,
        next_teacher_goal: str,
        current_question: str | None,
        student_answer_status: str,
    ) -> RagTurnContext:
        session = lesson_detail.session if lesson_detail is not None else None
        session_messages = (
            format_message_lines(lesson_detail.messages) if lesson_detail is not None else []
        )
        return RagTurnContext(
            query=query or message,
            current_chapter_id=session.current_chapter_id or "" if session is not None else "",
            current_section_id=session.current_section_id or "" if session is not None else "",
            current_knowledge_point_id=(
                session.current_knowledge_point_id or "" if session is not None else ""
            ),
            current_skill_id=session.current_skill_id or "" if session is not None else "",
            teaching_mode=teaching_mode,
            learner_state=learner_state,
            next_teacher_goal=next_teacher_goal,
            current_question=current_question or "",
            student_answer_status=student_answer_status,
            recent_messages=session_messages,
        )

    def _lesson_state_from_skill(
        self,
        skill: TeachingSkill,
        lesson_detail: LessonSessionDetail | None = None,
    ) -> dict[str, str | None]:
        target = skill.target or {}
        knowledge_points = target.get("knowledge_points", [])
        chapters = target.get("chapters", [])
        sections = target.get("sections", [])
        session = lesson_detail.session if lesson_detail is not None else None
        return {
            "current_skill_id": skill.id,
            "current_knowledge_point_id": (
                str(knowledge_points[0])
                if knowledge_points
                else session.current_knowledge_point_id if session is not None else None
            ),
            "current_chapter_id": (
                str(chapters[0])
                if chapters
                else session.current_chapter_id if session is not None else None
            ),
            "current_section_id": (
                str(sections[0])
                if sections
                else session.current_section_id if session is not None else None
            ),
        }


def get_agent_harness() -> AgentHarness:
    lesson_repository = get_lesson_repository()
    memory_service = get_memory_service()
    rag_service = get_rag_service()
    return AgentHarness(
        memory_service=memory_service,
        rag_service=rag_service,
        skill_registry=get_skill_registry(),
        llm_provider=get_llm_provider(),
        lesson_repository=lesson_repository,
        deepagents_runtime=DeepAgentsTeachingRuntime(
            memory_service=memory_service,
            lesson_repository=lesson_repository,
            rag_service=rag_service,
        ),
        planner_service=get_planner_service(),
        memory_update_dispatcher=build_memory_update_dispatcher(memory_service),
    )
