from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.settings import settings


@dataclass(frozen=True)
class TeachingSkill:
    id: str
    name: str
    skill_type: str = "knowledge"
    guidance: str = ""


@dataclass(frozen=True)
class SkillSelection:
    core: TeachingSkill
    knowledge: TeachingSkill

    @property
    def response_skill_id(self) -> str:
        return self.knowledge.id


class SkillRegistry:
    def __init__(self, skills_dir: Path | None = None) -> None:
        self.skills_dir = skills_dir or settings.skills_dir

    def pick_skills(self, grade: str, subject: str) -> SkillSelection:
        return SkillSelection(
            core=self.get_core_skill(),
            knowledge=self.pick_knowledge_skill(grade, subject),
        )

    def get_core_skill(self) -> TeachingSkill:
        return self._load_skill("universal-teacher-core.yaml")

    def pick_knowledge_skill(self, grade: str, subject: str) -> TeachingSkill:
        if subject == "数学" and grade in {"初一", "初二", "初三"}:
            return self._load_skill("junior-math-linear-equation.yaml")

        return TeachingSkill(
            id="opent-teacher-general",
            name="通用严格但温暖教师 Skill",
            skill_type="knowledge",
            guidance=(
                "先诊断学生卡点，再给下一步提示；不要直接给可抄写答案；"
                "学生自我否定时先稳定情绪，再回到学习任务；"
                "下一步必须结合科目和学生当前输入，避免只说“告诉我条件/说说哪里不会”。"
                "语文阅读先要原文、题目和学生认为相关的句子；语文作文让学生发开头三句或先改一处表达。"
                "英语概念错误先点明错误规则和正确边界，再让学生判断一个词或一句话；"
                "英语背词困难时让学生立刻写 3 个单词的中文和例句。"
                "物理题先追问一个决定性状态或受力线索，例如漂浮/悬浮/下沉、是否接触、力的方向；"
                "数学题让学生重写当前一步、通分、列式或说明变形理由。"
            ),
        )

    def pick_skill(self, grade: str, subject: str) -> TeachingSkill:
        return self.pick_knowledge_skill(grade, subject)

    def _load_skill(self, filename: str) -> TeachingSkill:
        path = self.skills_dir / filename
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Teaching skill file is invalid: {path}")

        return TeachingSkill(
            id=str(raw["id"]),
            name=str(raw["name"]),
            skill_type=str(raw.get("skill_type", "knowledge")),
            guidance=self._build_guidance(raw),
        )

    def _build_guidance(self, raw: dict[str, Any]) -> str:
        parts: list[str] = []

        principles = raw.get("teaching_principles", [])
        if principles:
            parts.append("教学原则：" + "；".join(str(item) for item in principles))

        diagnosis = raw.get("diagnosis", {})
        if isinstance(diagnosis, dict):
            opening_questions = diagnosis.get("opening_questions", [])
            checkpoint_questions = diagnosis.get("checkpoint_questions", [])
            mastery_signals = diagnosis.get("mastery_signals", [])
            if opening_questions:
                parts.append("开场诊断问题：" + "；".join(str(item) for item in opening_questions))
            if checkpoint_questions:
                parts.append("过程检查问题：" + "；".join(str(item) for item in checkpoint_questions))
            if mastery_signals:
                parts.append("掌握信号：" + "；".join(str(item) for item in mastery_signals))

        learner_state_model = raw.get("learner_state_model", {})
        if isinstance(learner_state_model, dict):
            states = learner_state_model.get("states", [])
            formatted_states = []
            for state in states:
                if not isinstance(state, dict):
                    continue
                state_id = state.get("id", "")
                signs = "、".join(str(item) for item in state.get("signs", []))
                teacher_move = "、".join(str(item) for item in state.get("teacher_move", []))
                formatted_states.append(f"{state_id}：信号={signs}；教师动作={teacher_move}")
            if formatted_states:
                parts.append("学生状态模型：" + " | ".join(formatted_states))

        error_patterns = raw.get("error_patterns", [])
        if error_patterns:
            formatted_errors = []
            for pattern in error_patterns:
                if not isinstance(pattern, dict):
                    continue
                name = pattern.get("name", "")
                signs = "、".join(str(item) for item in pattern.get("signs", []))
                strategy = "、".join(str(item) for item in pattern.get("correction_strategy", []))
                practice = "、".join(str(item) for item in pattern.get("followup_practice", []))
                formatted_errors.append(f"{name}：表现={signs}；纠正={strategy}；练习={practice}")
            if formatted_errors:
                parts.append("常见错误模式：" + " | ".join(formatted_errors))

        response_policy = raw.get("response_policy", {})
        if isinstance(response_policy, dict):
            parts.append(
                "回答策略："
                + "；".join(f"{key}={value}" for key, value in response_policy.items())
            )

        safety = raw.get("safety", {})
        if isinstance(safety, dict):
            forbidden_behaviors = safety.get("forbidden_behaviors", [])
            privacy_notes = safety.get("privacy_notes", [])
            if forbidden_behaviors:
                parts.append("禁止行为：" + "；".join(str(item) for item in forbidden_behaviors))
            if privacy_notes:
                parts.append("隐私边界：" + "；".join(str(item) for item in privacy_notes))

        composition_policy = raw.get("composition_policy", {})
        if isinstance(composition_policy, dict):
            priority_order = composition_policy.get("priority_order", [])
            instructions = composition_policy.get("instructions", [])
            if priority_order:
                parts.append("组合优先级：" + " > ".join(str(item) for item in priority_order))
            if instructions:
                parts.append("组合规则：" + "；".join(str(item) for item in instructions))

        examples = raw.get("examples", [])
        if examples:
            formatted_examples = []
            for example in examples:
                if not isinstance(example, dict):
                    continue
                student = example.get("student", "")
                teacher = example.get("teacher", "")
                formatted_examples.append(f"学生：{student} -> 教师：{teacher}")
            if formatted_examples:
                parts.append("示例回复：" + " | ".join(formatted_examples))

        return "\n".join(parts)


@lru_cache
def get_skill_registry() -> SkillRegistry:
    return SkillRegistry()
