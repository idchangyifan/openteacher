from app.schemas.teacher import StudentContext, TeacherChatRequest
from app.services.planner import PlannerService
from app.services.skill_registry import SkillRegistry


def plan_for(message: str, *, subject: str = "数学"):
    skills = SkillRegistry().pick_skills("初一", subject)
    request = TeacherChatRequest(
        message=message,
        context=StudentContext(student_id="planner-test-student", subject=subject),
    )
    return PlannerService().plan(
        request,
        effective_subject=subject,
        skills=skills,
        memory_summary="移项符号容易错",
        lesson_detail=None,
    )


def test_planner_detects_mastery_signal_and_avoids_mechanical_step_demand() -> None:
    decision = plan_for("2(x-3)=10，我算出来 x=8")

    assert decision.learner_state == "mastery_signal"
    assert decision.teaching_mode == "review"
    assert "先确认学生已完成当前任务" in decision.next_teacher_goal
    assert "学生答对时必须先确认" in "；".join(decision.guardrail_notes)


def test_planner_detects_active_lesson_request() -> None:
    decision = plan_for("我想开始学浮力，不是做题", subject="物理")

    assert decision.teaching_mode == "active_lesson"
    assert decision.skill_selection_plan.knowledge_skill_id == "opent-teacher-general"
    assert "设定本轮学习目标" in decision.next_teacher_goal


def test_planner_detects_direct_answer_seeking() -> None:
    decision = plan_for("直接告诉我答案吧，我要抄。")

    assert decision.learner_state == "answer_seeking"
    assert decision.teaching_mode == "qa"
    assert "不能给可抄完整答案" in "；".join(decision.guardrail_notes)


def test_planner_prompt_context_is_structured() -> None:
    decision = plan_for("我移项不变号，为什么错？")

    context = decision.to_prompt_context()

    assert "teaching_mode=adaptive_remediation" in context
    assert "learner_state=step_error" in context
    assert "retrieve_student_memory" in context
