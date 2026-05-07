from app.schemas.teacher import StudentContext, TeacherChatRequest
from app.services.llm_provider import MockTeacherProvider, TeacherPrompt
from app.services.planner import PlannerService
from app.services.skill_registry import SkillRegistry


MASTERED_POSITIVE_NEGATIVE_MEMORY = (
    "长期记忆卡片（背景假设）：academic_signal:学生能够解释正数和负数表示相反意义的量 "
    "(learning_status=mastered; topic=kp-positive-negative-numbers; confidence=0.84; "
    "学习信号不等于已经掌握)"
)


def test_mock_teacher_does_not_restart_intro_when_memory_shows_mastery() -> None:
    reply = MockTeacherProvider().generate_reply(
        TeacherPrompt(
            message="开始教学",
            grade="高一",
            subject="数学",
            teacher_style="严格但温暖",
            skill_name="数学主动课堂",
            skill_guidance="",
            memory_summary=MASTERED_POSITIVE_NEGATIVE_MEMORY,
            retrieved_context="",
        )
    )

    assert "不从头重讲正负数" in reply
    assert "迁移题" in reply
    assert "完全没学过正数和负数" not in reply


def test_planner_uses_mastered_memory_to_review_instead_of_intro_diagnostic() -> None:
    skills = SkillRegistry().pick_skills("高一", "数学", message="开始教学")

    decision = PlannerService().plan(
        TeacherChatRequest(
            message="开始教学",
            context=StudentContext(student_id="memory-guided-start", grade="高一", subject="数学"),
        ),
        effective_subject="数学",
        skills=skills,
        memory_summary=MASTERED_POSITIVE_NEGATIVE_MEMORY,
        lesson_detail=None,
    )

    assert decision.teaching_mode == "review"
    assert "不要重新从正负数入门开始" in decision.next_teacher_goal
