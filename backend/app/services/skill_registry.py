from dataclasses import dataclass


@dataclass(frozen=True)
class TeachingSkill:
    id: str
    name: str


class SkillRegistry:
    def pick_skill(self, grade: str, subject: str) -> TeachingSkill:
        if subject == "数学" and grade in {"初一", "初二", "初三"}:
            return TeachingSkill(
                id="opent-teacher-junior-math-linear-equation",
                name="初中数学一元一次方程严格引导 Skill",
            )

        return TeachingSkill(
            id="opent-teacher-general",
            name="通用严格但温暖教师 Skill",
        )


def get_skill_registry() -> SkillRegistry:
    return SkillRegistry()
