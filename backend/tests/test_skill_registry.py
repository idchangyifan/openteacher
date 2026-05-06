from app.services.skill_registry import SkillRegistry


def test_skill_registry_combines_universal_core_with_knowledge_skill() -> None:
    skills = SkillRegistry().pick_skills("初一", "数学", message="2(x - 3) = 10，下一步怎么做？")

    assert skills.core.id == "opent-teacher-universal-core"
    assert skills.core.skill_type == "core"
    assert "学生状态模型" in skills.core.guidance
    assert "answer_seeking" in skills.core.guidance
    assert skills.knowledge.id == "opent-teacher-junior-math-linear-equation"
    assert skills.response_skill_id == skills.knowledge.id


def test_skill_registry_selects_generated_textbook_skill_from_message() -> None:
    skills = SkillRegistry().pick_skills("初一", "数学", message="老师，数轴的三要素是什么？")

    assert skills.knowledge.id == "opent-teacher-rj-junior-math-grade7-vol1-kp-number-line"
    assert skills.knowledge.review_status == "draft"
    assert "教材页码候选：第 14 - 15 页" in skills.knowledge.guidance
    assert "识别数轴三要素" in skills.knowledge.guidance


def test_skill_registry_uses_first_generated_skill_for_lesson_start() -> None:
    skills = SkillRegistry().pick_skills("初一", "数学", message="请开始教学")

    assert skills.knowledge.id == (
        "opent-teacher-rj-junior-math-grade7-vol1-kp-positive-negative-numbers"
    )
    assert "正数和负数" in skills.knowledge.name


def test_skill_registry_uses_universal_core_for_general_subjects() -> None:
    skills = SkillRegistry().pick_skills("初一", "语文")

    assert skills.core.id == "opent-teacher-universal-core"
    assert skills.knowledge.id == "opent-teacher-general"
    assert "避免只说" in skills.knowledge.guidance
    assert "作文让学生发开头三句" in skills.knowledge.guidance
    assert "漂浮/悬浮/下沉" in skills.knowledge.guidance


def test_universal_core_requires_concrete_next_actions() -> None:
    skills = SkillRegistry().pick_skills("初一", "英语")

    assert "concrete_next_action_policy" in skills.core.guidance
    assert "concept_error_policy" in skills.core.guidance
    assert "3 个最难的词" in skills.core.guidance
