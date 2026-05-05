from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.schemas.lesson import LessonSessionDetail
from app.schemas.teacher import TeacherChatRequest
from app.services.skill_registry import SkillSelection

TeachingMode = Literal[
    "active_lesson",
    "qa",
    "diagnostic_check",
    "concept_instruction",
    "guided_practice",
    "adaptive_remediation",
    "review",
    "lesson_summary",
]

LearnerState = Literal[
    "insufficient_information",
    "answer_seeking",
    "genuinely_stuck",
    "concept_error",
    "step_error",
    "mastery_signal",
    "emotional_distress",
    "safety_risk",
]


@dataclass(frozen=True)
class MemoryRetrievalPlan:
    query: str
    use_long_term_memory: bool = True
    use_recent_lesson_history: bool = True
    rationale: str = "结合学生长期情况和当前课堂状态，但当前回答优先。"


@dataclass(frozen=True)
class SkillSelectionPlan:
    core_skill_id: str
    knowledge_skill_id: str
    rationale: str


@dataclass(frozen=True)
class ToolPlan:
    tools: list[str] = field(default_factory=list)
    rationale: str = "按教学计划调用必要工具，不把工具结果当作最终答案。"


@dataclass(frozen=True)
class PlannerDecision:
    teaching_mode: TeachingMode
    learner_state: LearnerState
    next_teacher_goal: str
    memory_retrieval_plan: MemoryRetrievalPlan
    skill_selection_plan: SkillSelectionPlan
    tool_plan: ToolPlan
    guardrail_notes: list[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        guardrails = "；".join(self.guardrail_notes) if self.guardrail_notes else "遵守教师边界。"
        return "\n".join(
            [
                f"teaching_mode={self.teaching_mode}",
                f"learner_state={self.learner_state}",
                f"next_teacher_goal={self.next_teacher_goal}",
                f"memory_query={self.memory_retrieval_plan.query}",
                f"selected_core_skill={self.skill_selection_plan.core_skill_id}",
                f"selected_knowledge_skill={self.skill_selection_plan.knowledge_skill_id}",
                f"tool_plan={', '.join(self.tool_plan.tools) or 'none'}",
                f"guardrails={guardrails}",
            ]
        )


class PlannerService:
    """Plan the next teacher move before the runtime drafts a reply.

    This is intentionally rule-based for v1. The important architectural move is
    that planner output is explicit and testable; later we can replace or enrich
    these rules with a LangGraph/DeepAgents planner without changing the rest of
    the harness contract.
    """

    def plan(
        self,
        request: TeacherChatRequest,
        *,
        effective_subject: str,
        skills: SkillSelection,
        memory_summary: str,
        lesson_detail: LessonSessionDetail | None,
    ) -> PlannerDecision:
        learner_state = self._classify_learner_state(request.message)
        teaching_mode = self._choose_teaching_mode(request, learner_state, lesson_detail)
        next_teacher_goal = self._choose_next_teacher_goal(teaching_mode, learner_state)
        tools = self._choose_tools(request, learner_state, lesson_detail)
        memory_query = self._build_memory_query(
            request=request,
            effective_subject=effective_subject,
            learner_state=learner_state,
            memory_summary=memory_summary,
        )

        return PlannerDecision(
            teaching_mode=teaching_mode,
            learner_state=learner_state,
            next_teacher_goal=next_teacher_goal,
            memory_retrieval_plan=MemoryRetrievalPlan(query=memory_query),
            skill_selection_plan=SkillSelectionPlan(
                core_skill_id=skills.core.id,
                knowledge_skill_id=skills.response_skill_id,
                rationale=(
                    "核心 skill 约束教师行为和边界；知识 skill 提供当前学科/知识点教学策略。"
                ),
            ),
            tool_plan=ToolPlan(tools=tools),
            guardrail_notes=self._guardrail_notes(learner_state),
        )

    def _classify_learner_state(self, message: str) -> LearnerState:
        normalized = message.strip().lower()

        if any(word in normalized for word in ["不想活", "自杀", "伤害自己", "被打", "虐待"]):
            return "safety_risk"
        if any(word in normalized for word in ["笨", "学不会", "太难", "崩溃", "害怕"]):
            return "emotional_distress"
        if any(word in normalized for word in ["答案", "直接告诉", "抄"]):
            return "answer_seeking"
        if self._looks_like_mastery_signal(normalized):
            return "mastery_signal"
        if any(word in normalized for word in ["错", "为什么不对", "哪里错", "不变号", "负号"]):
            return "step_error"
        if any(word in normalized for word in ["概念", "不理解", "什么意思", "是什么"]):
            return "concept_error"
        if any(word in normalized for word in ["不会", "卡住", "下一步", "没思路"]):
            return "genuinely_stuck"
        if len(normalized) < 8:
            return "insufficient_information"
        return "insufficient_information"

    def _choose_teaching_mode(
        self,
        request: TeacherChatRequest,
        learner_state: LearnerState,
        lesson_detail: LessonSessionDetail | None,
    ) -> TeachingMode:
        if learner_state == "safety_risk":
            return "qa"
        if learner_state == "mastery_signal":
            return "review"
        if learner_state in {"concept_error", "genuinely_stuck"}:
            return "concept_instruction" if learner_state == "concept_error" else "guided_practice"
        if learner_state == "step_error":
            return "adaptive_remediation"
        if lesson_detail is not None and lesson_detail.session.mode == "active_lesson":
            phase = lesson_detail.session.current_phase
            if phase in {
                "concept_instruction",
                "diagnostic_check",
                "guided_practice",
                "adaptive_remediation",
                "lesson_summary",
            }:
                return phase
            return "active_lesson"
        if any(word in request.message for word in ["开始学", "给我上课", "讲一讲", "学一下"]):
            return "active_lesson"
        if learner_state == "answer_seeking":
            return "qa"
        return "diagnostic_check"

    def _choose_next_teacher_goal(
        self, teaching_mode: TeachingMode, learner_state: LearnerState
    ) -> str:
        if learner_state == "mastery_signal":
            return "先确认学生已完成当前任务，再用一句理由、检验或小结确认理解。"
        if learner_state == "answer_seeking":
            return "拒绝可抄答案，但给出一个能推进学习的最小下一步。"
        if learner_state == "step_error":
            return "定位具体错误来源，只修正一个关键步骤。"
        if learner_state == "concept_error":
            return "用短讲解澄清概念，再问一个诊断问题。"
        if learner_state == "emotional_distress":
            return "先稳定学生情绪，再把任务降到可完成的一小步。"
        if learner_state == "safety_risk":
            return "优先现实安全帮助，不继续普通教学。"
        if teaching_mode == "active_lesson":
            return "设定本轮学习目标，提出一个诊断问题启动课堂。"
        return "获取最小必要信息，判断学生当前卡点。"

    def _choose_tools(
        self,
        request: TeacherChatRequest,
        learner_state: LearnerState,
        lesson_detail: LessonSessionDetail | None,
    ) -> list[str]:
        tools = ["retrieve_student_memory"]
        if request.context.session_id or lesson_detail is not None:
            tools.append("load_lesson_state")
        if learner_state in {"mastery_signal", "step_error", "concept_error", "genuinely_stuck"}:
            tools.append("plan_next_teaching_move")
        if learner_state in {"mastery_signal", "step_error", "concept_error", "emotional_distress"}:
            tools.append("create_memory_extraction_hint")
        return tools

    def _build_memory_query(
        self,
        *,
        request: TeacherChatRequest,
        effective_subject: str,
        learner_state: LearnerState,
        memory_summary: str,
    ) -> str:
        return (
            f"subject={effective_subject}; learner_state={learner_state}; "
            f"message={request.message}; known_summary={memory_summary}"
        )

    def _guardrail_notes(self, learner_state: LearnerState) -> list[str]:
        notes = [
            "OpenTeacher 是完整老师，主动授课和答疑都要服务于真正学会。",
            "不要机械要求步骤；学生答对时必须先确认。",
        ]
        if learner_state == "answer_seeking":
            notes.append("不能给可抄完整答案。")
        if learner_state == "safety_risk":
            notes.append("安全风险优先现实帮助。")
        return notes

    def _looks_like_mastery_signal(self, message: str) -> bool:
        compact = message.replace(" ", "")
        return any(
            fragment in compact
            for fragment in ["x=8", "x＝8", "算出来", "做完了", "我会了", "左边右边都是"]
        )


def get_planner_service() -> PlannerService:
    return PlannerService()
