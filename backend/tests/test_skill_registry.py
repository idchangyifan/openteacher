from app.services.skill_registry import SkillRegistry


def test_skill_registry_combines_universal_core_with_knowledge_skill() -> None:
    skills = SkillRegistry().pick_skills("初一", "数学")

    assert skills.core.id == "opent-teacher-universal-core"
    assert skills.core.skill_type == "core"
    assert "学生状态模型" in skills.core.guidance
    assert "answer_seeking" in skills.core.guidance
    assert skills.knowledge.id == "opent-teacher-junior-math-linear-equation"
    assert skills.response_skill_id == skills.knowledge.id


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
