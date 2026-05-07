from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from langchain.agents.middleware import dynamic_prompt
from langchain.agents.middleware.types import AgentMiddleware
from langchain_openai import ChatOpenAI
from deepagents.middleware.memory import MemoryMiddleware
from pymongo import MongoClient

from app.core.settings import settings
from app.schemas.lesson import LessonSessionDetail
from app.schemas.teacher import TeacherChatRequest
from app.services.deepagents_memory import StaticMemoryBackend
from app.services.lesson_store import LessonRepository
from app.services.llm_provider import TeacherPrompt
from app.services.memory import MemoryService
from app.services.rag import RagService, RagTurnContext
from app.services.teaching_turn_context import (
    evaluate_student_answer,
    format_message_lines,
    infer_current_question,
)


@dataclass(frozen=True)
class TeachingLessonState:
    session_id: str | None
    title: str
    lesson_goal: str
    current_phase: str
    pending_student_action: str
    summary: str
    current_chapter_id: str | None = None
    current_section_id: str | None = None
    current_knowledge_point_id: str | None = None
    current_skill_id: str | None = None


@dataclass(frozen=True)
class TeachingGraphState:
    """State contract between OpenTeacher services and the LangGraph runtime."""

    thread_id: str
    student_id: str
    grade: str
    subject: str
    teacher_style: str
    messages: list[dict[str, str]]
    lesson_state: TeachingLessonState
    selected_skill: dict[str, str]
    current_question: str | None
    student_answer_status: str
    student_answer_feedback: str
    next_teaching_action: str
    retrieved_memory: str
    retrieved_chunks: str
    planner_context: str

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeepAgentsTeachingResult:
    reply: str
    diagnostics: dict[str, str]


class DeepAgentsTeachingRuntime:
    """LangChain DeepAgents adapter for OpenTeacher.

    This is the first harness-level integration. It intentionally keeps database
    access behind service/tool functions so the agent can plan teaching actions
    without knowing MongoDB collection details.
    """

    def __init__(
        self,
        memory_service: MemoryService,
        lesson_repository: LessonRepository,
        rag_service: RagService | None = None,
    ) -> None:
        self.memory_service = memory_service
        self.lesson_repository = lesson_repository
        self.rag_service = rag_service
        self._mongo_client: MongoClient | None = None

    def generate_reply(
        self,
        request: TeacherChatRequest,
        prompt: TeacherPrompt,
    ) -> DeepAgentsTeachingResult:
        create_deep_agent = self._load_create_deep_agent()
        graph_state = self._build_graph_state(request, prompt)
        agent = create_deep_agent(
            model=self._build_model(),
            tools=self._build_tools(request, prompt, graph_state),
            system_prompt=self._build_system_prompt(prompt),
            middleware=self._build_middleware(prompt, graph_state),
            checkpointer=self._build_checkpointer(),
        )
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": self._build_user_message(request, prompt, graph_state),
                    }
                ]
            },
            config=self._invoke_config(graph_state),
        )
        return DeepAgentsTeachingResult(
            reply=self._extract_reply(result),
            diagnostics={
                "runtime": "deepagents",
                "thread_id": graph_state.thread_id,
                "checkpointer": self._checkpointer_diagnostic(),
            },
        )

    def _load_create_deep_agent(self) -> Any:
        from deepagents import create_deep_agent

        return create_deep_agent

    def _build_model(self) -> ChatOpenAI | str:
        if settings.deepagents_model:
            return settings.deepagents_model

        if settings.llm_provider == "doubao" and settings.doubao_api_key and settings.doubao_model:
            return ChatOpenAI(
                api_key=settings.doubao_api_key.get_secret_value(),
                base_url=settings.doubao_base_url,
                model=settings.doubao_model,
                timeout=settings.doubao_timeout_seconds,
                max_tokens=settings.doubao_max_tokens,
                temperature=0.3,
            )

        if settings.llm_provider == "openai" and settings.openai_api_key and settings.openai_model:
            return ChatOpenAI(
                api_key=settings.openai_api_key.get_secret_value(),
                base_url=settings.openai_base_url,
                model=settings.openai_model,
                timeout=settings.openai_timeout_seconds,
                max_tokens=settings.openai_max_output_tokens,
                temperature=0.3,
            )

        raise ValueError("DeepAgents runtime requires DEEPAGENTS_MODEL or a configured LLM provider")

    def _build_checkpointer(self) -> Any | None:
        if settings.lesson_store_backend != "mongodb":
            return None

        from langgraph.checkpoint.mongodb import MongoDBSaver

        client = self._get_mongo_client()
        return MongoDBSaver(
            client,
            db_name=settings.mongodb_database,
            checkpoint_collection_name="langgraph_checkpoints",
            writes_collection_name="langgraph_checkpoint_writes",
        )

    def _get_mongo_client(self) -> MongoClient:
        if self._mongo_client is None:
            self._mongo_client = MongoClient(settings.mongodb_uri)
        return self._mongo_client

    def _checkpointer_diagnostic(self) -> str:
        return "mongodb" if settings.lesson_store_backend == "mongodb" else "none"

    def _build_tools(
        self,
        request: TeacherChatRequest,
        prompt: TeacherPrompt | None = None,
        graph_state: TeachingGraphState | None = None,
    ) -> list[Any]:
        def retrieve_student_memory(query: str) -> str:
            """Retrieve teaching memories for the current student and query."""

            detail = self._load_session_detail(request)
            summary = self.memory_service.get_student_summary(
                request.context.student_id,
                subject=request.context.subject,
                lesson_detail=detail,
                recent_lessons=self._recent_lesson_summaries(
                    request.context.student_id,
                    request.context.subject,
                    request.context.grade,
                ),
            )
            return (
                f"学生：{request.context.student_id}\n"
                f"查询：{query}\n"
                f"当前可用记忆摘要：{summary}\n"
                "注意：记忆只能作为教学假设，不能替代当前学生回答。"
            )

        def load_lesson_state() -> str:
            """Load the current lesson state and recent messages if a session is active."""

            session_id = request.context.session_id
            if not session_id:
                return "当前没有绑定课堂 session。请按主动授课模式先设定本轮学习目标。"

            detail = self.lesson_repository.get_session_detail(session_id)
            if detail is None:
                return f"未找到课堂 session：{session_id}"

            transcript = "\n".join(format_message_lines(detail.messages))
            if not transcript:
                transcript = "(当前 session 暂无历史消息)"
            return (
                f"课堂标题：{detail.session.title}\n"
                f"课堂目标：{detail.session.lesson_goal}\n"
                f"当前阶段：{detail.session.current_phase}\n"
                f"待学生行动：{detail.session.pending_student_action}\n"
                f"当前章节：{detail.session.current_chapter_id or '未设置'}\n"
                f"当前小节：{detail.session.current_section_id or '未设置'}\n"
                f"当前知识点：{detail.session.current_knowledge_point_id or '未设置'}\n"
                f"当前 skill：{detail.session.current_skill_id or '未设置'}\n"
                f"课堂摘要：{detail.session.summary}\n"
                f"完整课堂消息：\n{transcript}"
            )

        def plan_next_teaching_move(learner_state: str, evidence: str) -> str:
            """Reflect on the next teacher move for active teaching or Q&A."""

            return (
                "请像真实老师一样先理解学生这一句话的意图，再选择下一步回应。\n"
                "把 planner、lesson state 和 RAG 当作材料，不要当作固定脚本。\n"
                "可选动作包括：确认学生已经做对的部分、换一个问法、给一个小提示、"
                "用生活情境解释、追问理由、给一题很短的变式练习。\n"
                "如果学生卡住，不要反复宣布“我来判断卡点”，而是直接用一句自然的提示"
                "帮助学生往前走；如果学生已经答对，不必要求从头重写，可以追问为什么。\n"
                "如果是答疑，不要变成答案机器，也不要机械套用主动授课开场。\n"
                f" learner_state={learner_state}\n evidence={evidence}"
            )

        def retrieve_textbook_chunks(query: str = "") -> str:
            """Retrieve textbook chunks using current lesson state and teaching intent."""

            if self.rag_service is None:
                return "当前 DeepAgents runtime 未配置教材 RAG service。"
            state = graph_state or self._build_graph_state(request, prompt or self._empty_prompt())
            context = RagTurnContext(
                query=query or request.message,
                current_chapter_id=state.lesson_state.current_chapter_id or "",
                current_section_id=state.lesson_state.current_section_id or "",
                current_knowledge_point_id=state.lesson_state.current_knowledge_point_id or "",
                current_skill_id=state.lesson_state.current_skill_id or "",
                teaching_mode=self._extract_planner_field(
                    state.planner_context,
                    "teaching_mode",
                ),
                learner_state=self._extract_planner_field(
                    state.planner_context,
                    "learner_state",
                ),
                next_teacher_goal=state.next_teaching_action,
                current_question=state.current_question or "",
                student_answer_status=state.student_answer_status,
                recent_messages=format_message_lines(state.messages),
            )
            return self.rag_service.retrieve_for_turn(context)

        def create_memory_extraction_hint(summary: str) -> str:
            """Record a candidate memory extraction hint for later structured memory extraction."""

            return (
                "已记录为候选记忆抽取提示，后续应由 MemoryExtractionService 校验后写入 "
                f"memory_cards。候选摘要：{summary}"
            )

        return [
            retrieve_student_memory,
            load_lesson_state,
            plan_next_teaching_move,
            retrieve_textbook_chunks,
            create_memory_extraction_hint,
        ]

    def _build_middleware(
        self,
        prompt: TeacherPrompt,
        graph_state: TeachingGraphState,
    ) -> list[AgentMiddleware]:
        @dynamic_prompt
        def opent_teacher_short_term_context(_request: Any) -> str:
            return "\n\n".join(
                [
                    self._build_system_prompt(prompt),
                    self._format_short_term_context(graph_state),
                ]
            )

        return [
            opent_teacher_short_term_context,
            self._build_student_memory_middleware(graph_state),
        ]

    def _build_student_memory_middleware(
        self,
        graph_state: TeachingGraphState,
    ) -> MemoryMiddleware:
        memory_path = "/openteacher/student-memory.md"
        lesson_detail = self.lesson_repository.get_session_detail(
            graph_state.lesson_state.session_id
        ) if graph_state.lesson_state.session_id else None
        memory_text = self.memory_service.format_deepagents_memory(
            student_id=graph_state.student_id,
            subject=graph_state.subject,
            lesson_detail=lesson_detail,
            recent_lessons=self._recent_lesson_summaries(
                graph_state.student_id,
                graph_state.subject,
                graph_state.grade,
            ),
        )
        return MemoryMiddleware(
            backend=StaticMemoryBackend({memory_path: memory_text}),
            sources=[memory_path],
        )

    def _format_short_term_context(self, graph_state: TeachingGraphState) -> str:
        transcript = "\n".join(format_message_lines(graph_state.messages))
        if not transcript:
            transcript = "(当前 session 暂无历史消息)"
        return (
            "<open_teacher_short_term_memory>\n"
            "这是当前课堂 thread 的短期记忆，由 DeepAgents middleware 在模型调用前注入。\n"
            "把学生最新输入理解为这段课堂的延续；只有学生明确要求换课或重开时，才重启课程。\n"
            f"thread_id: {graph_state.thread_id}\n"
            f"current_skill_id: {graph_state.lesson_state.current_skill_id or 'none'}\n"
            f"current_knowledge_point_id: {graph_state.lesson_state.current_knowledge_point_id or 'none'}\n"
            f"current_question: {graph_state.current_question or 'none'}\n"
            f"student_answer_status: {graph_state.student_answer_status}\n"
            f"student_answer_feedback: {graph_state.student_answer_feedback or 'none'}\n"
            f"next_teaching_action: {graph_state.next_teaching_action or 'none'}\n"
            "如果 current_question 不是 none 且 student_answer_status 不是 correct，"
            "优先回应当前回答本身，避免重新宣布学习目标或回到 lesson_start。\n"
            "可以先承认学生回答里的合理尝试，再指出差异，换一种问法或给一个小提示。\n"
            "回复要像课堂里的自然对话；不要使用 Markdown 标题，不要输出 ### 学习目标 / ### 诊断问题 这类结构标题。\n"
            "完整课堂记录：\n"
            f"{transcript}\n"
            "</open_teacher_short_term_memory>"
        )

    def _empty_prompt(self) -> TeacherPrompt:
        return TeacherPrompt(
            message="",
            grade="",
            subject="",
            teacher_style="严格但温暖",
            skill_name="",
            skill_guidance="",
            memory_summary="",
            retrieved_context="",
            core_skill_name="",
            core_skill_guidance="",
            knowledge_skill_name="",
            knowledge_skill_guidance="",
            planner_context="",
        )

    def _build_graph_state(
        self,
        request: TeacherChatRequest,
        prompt: TeacherPrompt,
    ) -> TeachingGraphState:
        lesson_detail = self._load_session_detail(request)
        lesson_state = self._build_lesson_state(request, lesson_detail)
        messages = self._build_state_messages(request, lesson_detail)
        current_question = infer_current_question(messages)
        answer_evaluation = evaluate_student_answer(current_question, request.message)
        return TeachingGraphState(
            thread_id=self._thread_id(request),
            student_id=request.context.student_id,
            grade=request.context.grade,
            subject=request.context.subject,
            teacher_style=request.context.teacher_style,
            messages=messages,
            lesson_state=lesson_state,
            selected_skill={
                "core": prompt.effective_core_skill_name,
                "knowledge": prompt.effective_knowledge_skill_name,
            },
            current_question=current_question,
            student_answer_status=answer_evaluation.status,
            student_answer_feedback=answer_evaluation.feedback,
            next_teaching_action=answer_evaluation.feedback or self._extract_planner_field(
                prompt.planner_context,
                "next_teacher_goal",
            ),
            retrieved_memory=prompt.memory_summary,
            retrieved_chunks=prompt.retrieved_context,
            planner_context=prompt.planner_context or "",
        )

    def _load_session_detail(self, request: TeacherChatRequest) -> LessonSessionDetail | None:
        if not request.context.session_id:
            return None
        return self.lesson_repository.get_session_detail(request.context.session_id)

    def _recent_lesson_summaries(self, student_id: str, subject: str, grade: str):
        return [
            session
            for session in self.lesson_repository.list_sessions(student_id)
            if session.subject == subject and session.grade == grade
        ][:3]

    def _build_lesson_state(
        self,
        request: TeacherChatRequest,
        lesson_detail: LessonSessionDetail | None,
    ) -> TeachingLessonState:
        if lesson_detail is None:
            return TeachingLessonState(
                session_id=request.context.session_id,
                title="",
                lesson_goal="",
                current_phase="active_lesson",
                pending_student_action="",
                summary="",
            )
        session = lesson_detail.session
        return TeachingLessonState(
            session_id=session.id,
            title=session.title,
            lesson_goal=session.lesson_goal,
            current_phase=session.current_phase,
            pending_student_action=session.pending_student_action,
            summary=session.summary,
            current_chapter_id=session.current_chapter_id,
            current_section_id=session.current_section_id,
            current_knowledge_point_id=session.current_knowledge_point_id,
            current_skill_id=session.current_skill_id,
        )

    def _build_state_messages(
        self,
        request: TeacherChatRequest,
        lesson_detail: LessonSessionDetail | None,
    ) -> list[dict[str, str]]:
        if lesson_detail is None:
            return [{"role": "student", "content": request.message}]
        return [
            {"role": message.role, "content": message.content}
            for message in lesson_detail.messages
        ]

    def _extract_planner_field(self, planner_context: str, field_name: str) -> str:
        prefix = f"{field_name}="
        for line in planner_context.splitlines():
            if line.startswith(prefix):
                return line[len(prefix) :].strip()
        return ""

    def _thread_id(self, request: TeacherChatRequest) -> str:
        return request.context.session_id or f"student:{request.context.student_id}"

    def _invoke_config(self, graph_state: TeachingGraphState) -> dict[str, Any]:
        return {
            "configurable": {
                "thread_id": graph_state.thread_id,
            },
            "metadata": {
                "student_id": graph_state.student_id,
                "session_id": graph_state.lesson_state.session_id,
                "current_skill_id": graph_state.lesson_state.current_skill_id,
            },
        }

    def _build_system_prompt(self, prompt: TeacherPrompt) -> str:
        return (
            "你是 OpenTeacher harness agent 的 Executor，由 LangChain DeepAgents runtime 执行。"
            "Planner 已经给出本轮结构化教学计划；它是工作假设，不是固定脚本。"
            "你应结合当前学生输入、课堂记录、教材依据和学生状态，做出像真实老师一样的临场判断。"
            "OpenTeacher 是真正的老师，主动授课是主轴，被动答疑只是其中一种能力。"
            "每轮先判断当前模式：active_lesson、qa、diagnostic_check、guided_practice、"
            "review 或 lesson_summary。不要把所有输入都当成一元一次方程解题。"
            "需要时使用工具读取课堂状态、学生记忆和教材 chunks；记忆只能作为教学假设，"
            "当前学生回答永远优先。"
            "需要教材依据或下一步材料时，调用 retrieve_textbook_chunks；"
            "该工具会基于当前 lesson state、学生回答状态和 planner 意图做多路召回与 rerank。"
            "如果学生已经答对或完成当前任务，先确认正确，不要机械要求从头写步骤；"
            "再要求一句理由、验算、总结或进入下一教学阶段。"
            "如果 TeachingGraphState 中 student_answer_status 是 incorrect_symbol、"
            "invalid_symbol、incorrect_sign 或 stuck，默认停留在当前问题，"
            "用自然提示帮助学生自己修正；不要直接泄露完整答案，也不要突然切换到下一题。"
            "如果 student_answer_status 是 correct，先确认正确，再追问理由或做小结。"
            "不要使用 Markdown 标题，不要输出 ### 学习目标 / ### 诊断问题 这类结构标题。"
            "不要反复显式说“判断卡点”；把判断留在内部，直接给学生一个有帮助的回应。"
            "允许根据学生语气随机应变：可以鼓励、类比、换问法、承认合理尝试，"
            "但不要失去教师边界。"
            "如果学生想抄答案，坚定拒绝，但仍给出可学习的下一步。"
            "如果信息不足，要求最小必要信息。"
            "回复使用中文，短而清楚，体现完整老师的课程推进能力。\n"
            f"教师风格：{prompt.teacher_style}\n"
            f"教师核心 Skill：{prompt.effective_core_skill_name}\n"
            f"教师核心规则：\n{prompt.effective_core_skill_guidance}\n"
            f"知识点 Skill：{prompt.effective_knowledge_skill_name}\n"
            f"知识点规则：\n{prompt.effective_knowledge_skill_guidance}\n"
            f"Planner 决策：\n{prompt.planner_context or '未提供结构化 planner 决策。'}"
        )

    def _build_user_message(
        self,
        request: TeacherChatRequest,
        prompt: TeacherPrompt,
        graph_state: TeachingGraphState | None = None,
    ) -> str:
        if graph_state is None:
            graph_state = self._build_graph_state(request, prompt)
        return "\n".join(
            [
                f"年级：{request.context.grade}",
                f"科目：{request.context.subject}",
                f"thread_id：{graph_state.thread_id}",
                f"session_id：{graph_state.lesson_state.session_id or 'none'}",
                f"当前 skill：{graph_state.lesson_state.current_skill_id or 'none'}",
                f"当前知识点：{graph_state.lesson_state.current_knowledge_point_id or 'none'}",
                f"当前问题：{graph_state.current_question or 'none'}",
                f"学生回答状态：{graph_state.student_answer_status}",
                f"学生回答评价：{graph_state.student_answer_feedback or 'none'}",
                f"下一步教学动作：{graph_state.next_teaching_action or 'none'}",
                f"记忆摘要：{graph_state.retrieved_memory}",
                f"检索上下文：{graph_state.retrieved_chunks}",
                f"Planner 决策：{prompt.planner_context or 'none'}",
                f"学生消息：{request.message}",
            ]
        )

    def _extract_reply(self, result: Any) -> str:
        messages = result.get("messages") if isinstance(result, dict) else None
        if isinstance(messages, list) and messages:
            last_message = messages[-1]
            content = getattr(last_message, "content", None)
            if isinstance(last_message, dict):
                content = last_message.get("content", content)
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                chunks = []
                for item in content:
                    if isinstance(item, dict):
                        text = item.get("text") or item.get("content")
                        if isinstance(text, str):
                            chunks.append(text)
                text = "".join(chunks).strip()
                if text:
                    return text

        if isinstance(result, dict):
            for key in ("output", "reply", "content"):
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        raise ValueError("DeepAgents result did not contain a teacher reply")
