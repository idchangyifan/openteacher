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
    target: dict[str, Any] | None = None
    selection_keywords: tuple[str, ...] = ()
    review_status: str = ""


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

    def pick_skills(
        self,
        grade: str,
        subject: str,
        message: str = "",
        current_skill_id: str | None = None,
    ) -> SkillSelection:
        return SkillSelection(
            core=self.get_core_skill(),
            knowledge=self.pick_knowledge_skill(
                grade,
                subject,
                message,
                current_skill_id=current_skill_id,
            ),
        )

    def get_core_skill(self) -> TeachingSkill:
        return self._load_skill("universal-teacher-core.yaml")

    def pick_knowledge_skill(
        self,
        grade: str,
        subject: str,
        message: str = "",
        current_skill_id: str | None = None,
    ) -> TeachingSkill:
        current_skill = self.get_knowledge_skill_by_id(current_skill_id)
        if (
            current_skill is not None
            and self._target_matches(current_skill, grade, subject)
            and self._looks_like_continuation_message(message)
        ):
            return current_skill

        if self._looks_like_equation_message(message) and subject == "数学":
            return self._load_skill("junior-math-linear-equation.yaml")

        generated_skill = self._pick_generated_knowledge_skill(grade, subject, message)
        if generated_skill is not None:
            return generated_skill

        if current_skill is not None and self._target_matches(current_skill, grade, subject):
            return current_skill

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

    def pick_skill(
        self,
        grade: str,
        subject: str,
        message: str = "",
        current_skill_id: str | None = None,
    ) -> TeachingSkill:
        return self.pick_knowledge_skill(
            grade,
            subject,
            message,
            current_skill_id=current_skill_id,
        )

    def get_knowledge_skill_by_id(self, skill_id: str | None) -> TeachingSkill | None:
        if not skill_id:
            return None
        if skill_id == "opent-teacher-junior-math-linear-equation":
            return self._load_skill("junior-math-linear-equation.yaml")
        for skill in self._load_generated_knowledge_skills():
            if skill.id == skill_id:
                return skill
        return None

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
            target=raw.get("target") if isinstance(raw.get("target"), dict) else None,
            selection_keywords=self._selection_keywords(raw),
            review_status=str(raw.get("review_status", "")),
        )

    def _pick_generated_knowledge_skill(
        self, grade: str, subject: str, message: str
    ) -> TeachingSkill | None:
        generated_skills = [
            skill
            for skill in self._load_generated_knowledge_skills()
            if self._target_matches(skill, grade, subject)
        ]
        all_subject_generated_skills = [
            skill
            for skill in self._load_generated_knowledge_skills()
            if self._subject_matches(skill, subject)
        ]
        if (
            subject == "数学"
            and all_subject_generated_skills
            and (
                self._looks_like_lesson_start(message)
                or self._looks_like_course_placement_question(message)
            )
        ):
            candidate_skills = generated_skills or all_subject_generated_skills
            return sorted(candidate_skills, key=self._course_order_key)[0]

        if not generated_skills:
            return None

        scored = [
            (self._message_match_score(skill, message), skill)
            for skill in generated_skills
        ]
        best_score, best_skill = max(scored, key=lambda item: (item[0], item[1].id))
        if best_score > 0:
            return best_skill

        if subject == "数学" and grade in {"初一", "七年级"} and self._looks_like_lesson_start(message):
            return sorted(generated_skills, key=self._course_order_key)[0]

        if subject == "数学" and grade in {"初一", "七年级"}:
            return sorted(generated_skills, key=self._course_order_key)[0]

        return None

    def _course_order_key(self, skill: TeachingSkill) -> tuple[int, str]:
        target = skill.target or {}
        page_range = target.get("page_range", {})
        start_page = page_range.get("start") if isinstance(page_range, dict) else None
        return (int(start_page) if start_page is not None else 9999, skill.id)

    def _load_generated_knowledge_skills(self) -> list[TeachingSkill]:
        generated_dir = self.skills_dir / "generated"
        if not generated_dir.exists():
            return []

        skills = []
        for path in sorted(generated_dir.glob("*.yaml")):
            skill = self._load_skill(f"generated/{path.name}")
            if skill.skill_type == "knowledge":
                skills.append(skill)
        return skills

    def _target_matches(self, skill: TeachingSkill, grade: str, subject: str) -> bool:
        target = skill.target or {}
        subjects = {str(item) for item in target.get("subjects", [])}
        grades = {str(item) for item in target.get("grades", [])}
        grade_aliases = self._grade_aliases(grade)
        return (not subjects or subject in subjects) and (not grades or bool(grades & grade_aliases))

    def _subject_matches(self, skill: TeachingSkill, subject: str) -> bool:
        target = skill.target or {}
        subjects = {str(item) for item in target.get("subjects", [])}
        return not subjects or subject in subjects

    def _message_match_score(self, skill: TeachingSkill, message: str) -> int:
        normalized = message.lower().strip()
        if not normalized:
            return 0

        score = 0
        for keyword in skill.selection_keywords:
            keyword_normalized = keyword.lower().strip()
            if not keyword_normalized:
                continue
            if keyword_normalized in normalized:
                score += max(1, min(len(keyword_normalized), 12))

        target = skill.target or {}
        for knowledge_point_id in target.get("knowledge_points", []):
            if str(knowledge_point_id).lower() in normalized:
                score += 20
        return score

    def _grade_aliases(self, grade: str) -> set[str]:
        aliases = {grade}
        if grade == "初一":
            aliases.update({"七年级", "7年级", "七上"})
        if grade == "初二":
            aliases.update({"八年级", "8年级"})
        if grade == "初三":
            aliases.update({"九年级", "9年级"})
        return aliases

    def _looks_like_equation_message(self, message: str) -> bool:
        normalized = message.lower().replace(" ", "")
        return any(
            token in normalized
            for token in ["方程", "移项", "去括号", "x=", "=x", "2(x", "x-"]
        )

    def _looks_like_lesson_start(self, message: str) -> bool:
        return any(
            token in message
            for token in [
                "开始学",
                "开始教学",
                "开始上课",
                "给我上课",
                "讲一讲",
                "学一下",
                "今天学",
                "请开始",
                "主动教学",
                "继续教学",
                "继续上课",
                "上课",
            ]
        )

    def _looks_like_course_placement_question(self, message: str) -> bool:
        return "负数" in message and any(
            token in message
            for token in [
                "先教",
                "先学",
                "先讲",
                "不先",
                "应该先",
                "为什么",
                "顺序",
            ]
        )

    def _looks_like_continuation_message(self, message: str) -> bool:
        return any(
            token in message
            for token in [
                "上堂课",
                "上节课",
                "上一节",
                "上次",
                "刚才",
                "继续",
                "讲到哪",
                "讲到哪里",
                "讲了什么",
                "学了什么",
                "复习一下",
                "接着",
            ]
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

        target = raw.get("target", {})
        if isinstance(target, dict):
            knowledge_points = target.get("knowledge_points", [])
            page_range = target.get("page_range", {})
            if knowledge_points:
                parts.append("适用知识点：" + "；".join(str(item) for item in knowledge_points))
            if isinstance(page_range, dict) and page_range.get("start") is not None:
                parts.append(
                    f"教材页码候选：第 {page_range.get('start')} - {page_range.get('end')} 页"
                )

        source_evidence = raw.get("source_evidence", [])
        if source_evidence:
            formatted_evidence = []
            for item in source_evidence:
                if not isinstance(item, dict):
                    continue
                page_range = item.get("page_range", {})
                formatted_evidence.append(
                    f"{item.get('source_ref', '')} 页码={page_range.get('start')}-{page_range.get('end')} 备注={item.get('note', '')}"
                )
            if formatted_evidence:
                parts.append("来源证据：" + " | ".join(formatted_evidence))

        teaching_plan = raw.get("teaching_plan", {})
        if isinstance(teaching_plan, dict):
            plan_parts = []
            for key, label in [
                ("learning_objectives", "学习目标"),
                ("prerequisites", "前置知识"),
                ("opening", "导入方式"),
                ("practice_sequence", "练习顺序"),
                ("mastery_checks", "掌握检查"),
            ]:
                values = teaching_plan.get(key, [])
                if values:
                    plan_parts.append(f"{label}=" + "；".join(str(item) for item in values))
            if plan_parts:
                parts.append("教学设计：" + " | ".join(plan_parts))

        return "\n".join(parts)

    def _selection_keywords(self, raw: dict[str, Any]) -> tuple[str, ...]:
        selection = raw.get("selection", {})
        if not isinstance(selection, dict):
            return ()
        keywords = selection.get("keywords", [])
        if not isinstance(keywords, list):
            return ()
        return tuple(str(item) for item in keywords if str(item).strip())


@lru_cache
def get_skill_registry() -> SkillRegistry:
    return SkillRegistry()
