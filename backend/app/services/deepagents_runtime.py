from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_openai import ChatOpenAI

from app.core.settings import settings
from app.schemas.teacher import TeacherChatRequest
from app.services.lesson_store import LessonRepository
from app.services.llm_provider import TeacherPrompt
from app.services.memory import MemoryService


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

    def generate_reply(
        self,
        request: TeacherChatRequest,
        prompt: TeacherPrompt,
    ) -> DeepAgentsTeachingResult:
        create_deep_agent = self._load_create_deep_agent()
        agent = create_deep_agent(
            model=self._build_model(),
            tools=self._build_tools(request),
            system_prompt=self._build_system_prompt(prompt),
        )
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": self._build_user_message(request, prompt),
                    }
                ]
            }
        )
        return DeepAgentsTeachingResult(
            reply=self._extract_reply(result),
            diagnostics={"runtime": "deepagents"},
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

    def _build_user_message(self, request: TeacherChatRequest, prompt: TeacherPrompt) -> str:
        return "\n".join(
            [
                f"年级：{request.context.grade}",
                f"科目：{request.context.subject}",
                f"session_id：{request.context.session_id or 'none'}",
                f"记忆摘要：{prompt.memory_summary}",
                f"检索上下文：{prompt.retrieved_context}",
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
