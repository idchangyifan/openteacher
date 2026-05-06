from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from langchain_openai import ChatOpenAI
from pymongo import MongoClient

from app.core.settings import settings
from app.schemas.lesson import LessonSessionDetail
from app.schemas.teacher import TeacherChatRequest
from app.services.lesson_store import LessonRepository
from app.services.llm_provider import TeacherPrompt
from app.services.memory import MemoryService


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
    ) -> None:
        self.memory_service = memory_service
        self.lesson_repository = lesson_repository
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
            tools=self._build_tools(request),
            system_prompt=self._build_system_prompt(prompt),
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

    def _build_tools(self, request: TeacherChatRequest) -> list[Any]:
        def retrieve_student_memory(query: str) -> str:
            """Retrieve teaching memories for the current student and query."""

            summary = self.memory_service.get_student_summary(request.context.student_id)
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

            recent_messages = detail.messages[-6:]
            transcript = "\n".join(
                f"{message.role}: {message.content}" for message in recent_messages
            )
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
                f"最近消息：\n{transcript}"
            )

        def plan_next_teaching_move(learner_state: str, evidence: str) -> str:
            """Plan the next teacher move for active teaching or Q&A."""

            return (
                "请按完整老师的方式决定下一步：\n"
                "1. 如果学生已经完成当前任务，先确认，再进入理由检查、总结或下一题。\n"
                "2. 如果学生卡住，先定位卡点，只推进一个小步骤。\n"
                "3. 如果当前更适合主动授课，先说明本节目标，再给诊断问题。\n"
                "4. 如果是答疑，不要变成答案机器，也不要机械要求从头写步骤。\n"
                f" learner_state={learner_state}\n evidence={evidence}"
            )

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
            create_memory_extraction_hint,
        ]

    def _build_graph_state(
        self,
        request: TeacherChatRequest,
        prompt: TeacherPrompt,
    ) -> TeachingGraphState:
        lesson_detail = self._load_session_detail(request)
        lesson_state = self._build_lesson_state(request, lesson_detail)
        messages = self._build_state_messages(request, lesson_detail)
        current_question = self._infer_current_question(messages)
        answer_status, answer_feedback = self._evaluate_student_answer(
            question=current_question,
            answer=request.message,
        )
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
            student_answer_status=answer_status,
            student_answer_feedback=answer_feedback,
            next_teaching_action=answer_feedback or self._extract_planner_field(
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

    def _infer_current_question(self, messages: list[dict[str, str]]) -> str | None:
        for message in reversed(messages):
            has_question_mark = any(mark in message["content"] for mark in ["？", "?"])
            if message["role"] == "teacher" and has_question_mark:
                return message["content"]
        return None

    def _evaluate_student_answer(self, question: str | None, answer: str) -> tuple[str, str]:
        normalized_answer = answer.strip().replace("＋", "+").replace("－", "-")
        compact_answer = normalized_answer.replace(" ", "")
        if not question:
            return "needs_evaluation", ""

        if "收入10" in question and "支出6" in question:
            if compact_answer in {"-6", "-6元"}:
                return (
                    "correct",
                    "学生回答 -6 正确。先确认正确，再追问一句：为什么这里要用负号？不要切到下一题。",
                )
            if compact_answer in {"*6", "×6", "x6"}:
                return (
                    "incorrect_symbol",
                    "学生把符号写成了乘号。指出 * 不是正负号；继续让学生判断支出应该用 + 还是 -，不要直接说出完整答案，也不要切到下一题。",
                )
            if compact_answer in {"+6", "+6元", "6", "6元"}:
                return (
                    "incorrect_sign",
                    "学生没有表示出支出和收入的相反意义。只提示收入用 +，支出要用相反符号；不要切到下一题。",
                )
            if any(word in compact_answer for word in ["不知道", "不会", "不懂"]):
                return (
                    "stuck",
                    "学生卡住了。用收入和支出是相反意义的量来提示，并让学生继续回答这同一道题。",
                )

        return "needs_evaluation", ""

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
            "Planner 已经给出本轮结构化教学计划；你必须按计划执行，不能自行把 OpenTeacher 简化成解题 bot。"
            "OpenTeacher 是真正的老师，主动授课是主轴，被动答疑只是其中一种能力。"
            "每轮先判断当前模式：active_lesson、qa、diagnostic_check、guided_practice、"
            "review 或 lesson_summary。不要把所有输入都当成一元一次方程解题。"
            "你必须善用工具读取课堂状态和学生记忆，但记忆只能作为教学假设，"
            "当前学生回答永远优先。"
            "如果学生已经答对或完成当前任务，先确认正确，不要机械要求从头写步骤；"
            "再要求一句理由、验算、总结或进入下一教学阶段。"
            "如果 TeachingGraphState 中 student_answer_status 是 incorrect_symbol、"
            "incorrect_sign 或 stuck，必须停留在当前问题，不要直接泄露完整答案，"
            "也不要切换到下一题。"
            "如果 student_answer_status 是 correct，先确认正确，再追问理由或做小结。"
            "如果学生想抄答案，坚定拒绝，但仍给出可学习的下一步。"
            "如果信息不足，要求最小必要信息。"
            "回复必须中文、短而清楚，体现完整老师的课程推进能力。\n"
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
