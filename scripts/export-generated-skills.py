#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml


class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: object) -> bool:
        return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export TextbookToTeachingSkill skill_drafts as Teaching Skill YAML files."
    )
    parser.add_argument("--artifact", required=True, help="Pipeline artifact YAML path.")
    parser.add_argument("--output-dir", required=True, help="Directory for generated skills.")
    args = parser.parse_args()

    artifact_path = Path(args.artifact)
    output_dir = Path(args.output_dir)
    artifact = yaml.safe_load(artifact_path.read_text(encoding="utf-8"))
    if not isinstance(artifact, dict):
        raise SystemExit(f"Invalid pipeline artifact: {artifact_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    for skill in export_generated_skills(artifact):
        filename = f"{skill['id']}.yaml"
        (output_dir / filename).write_text(
            yaml.dump(
                skill,
                Dumper=NoAliasDumper,
                allow_unicode=True,
                sort_keys=False,
                width=100,
            ),
            encoding="utf-8",
        )


def export_generated_skills(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    manifest = artifact["textbook_manifest"]
    course_map = artifact["course_map"]
    knowledge_points = {item["id"]: item for item in artifact["knowledge_point_graph"]}
    chunks_by_kp = _chunks_by_knowledge_point(artifact.get("rag_chunks", []))

    skills = []
    for draft in artifact.get("skill_drafts", []):
        target_ids = list(draft["target_knowledge_point_ids"])
        first_kp = knowledge_points[target_ids[0]]
        teaching_plan = draft.get("teaching_plan") or {}
        page_range = _first_page_range(draft.get("evidence", []))
        chapter_ids = sorted({knowledge_points[kp_id]["chapter_id"] for kp_id in target_ids})
        chunk_ids = [
            chunk["id"]
            for kp_id in target_ids
            for chunk in chunks_by_kp.get(kp_id, [])
        ]
        skill_id = f"opent-teacher-{manifest['textbook_id']}-{target_ids[0]}"
        skill = {
            "id": skill_id,
            "name": f"{manifest['title']}：{first_kp['name']}",
            "version": artifact.get("version", "0.1.0"),
            "skill_type": "knowledge",
            "review_status": draft.get("review_status", "draft"),
            "target": {
                "school_stages": ["junior"],
                "grades": list(dict.fromkeys(["初一", "七年级", manifest.get("grade", "")])),
                "subjects": [manifest.get("subject", "")],
                "textbook_versions": [manifest["textbook_id"]],
                "chapters": chapter_ids,
                "knowledge_points": target_ids,
                "page_range": page_range,
            },
            "selection": {
                "keywords": _selection_keywords(first_kp, teaching_plan),
                "priority": 80,
            },
            "source_evidence": draft.get("evidence", []),
            "rag_chunk_refs": chunk_ids,
            "teaching_principles": [
                "围绕教材章节组织主动授课，不把学生输入只当成孤立题目。",
                "先诊断学生对本知识点的概念理解，再推进讲解、练习或纠错。",
                "所有教材事实和教学策略都保留来源、页码和审核状态，方便人工校验。",
            ],
            "diagnosis": {
                "opening_questions": teaching_plan.get("diagnosis_questions", []),
                "checkpoint_questions": teaching_plan.get("mastery_checks", []),
                "mastery_signals": teaching_plan.get("mastery_checks", []),
            },
            "error_patterns": _error_patterns(teaching_plan),
            "response_policy": {
                "direct_answer_policy": "不能直接给可抄答案；先提出一个与当前知识点有关的最小诊断问题或下一步。",
                "strictness_policy": "温暖但有要求；学生答对时先确认，再要求一句理由、检验或进入下一小节。",
                "praise_policy": "表扬要具体到概念、步骤或表达，不泛泛夸聪明。",
                "repeated_error_policy": "重复错误时回到教材情境或核心概念，只修正一个关键误区。",
                "uncertainty_policy": "如果教材页码、定义或例题证据不足，标记需要审核，不编造教材内容。",
            },
            "safety": {
                "forbidden_behaviors": [
                    "把 generated skill 当作已审核官方结论直接发布。",
                    "编造教材原文、页码或例题。",
                    "为了防抄答案而机械要求学生重写已经掌握的步骤。",
                ],
                "privacy_notes": [
                    "本 skill 只记录学习相关信息，不索要身份证号、精确住址或联系方式。"
                ],
            },
            "teaching_plan": teaching_plan,
        }
        skills.append(skill)

    return sorted(skills, key=lambda item: item["id"])


def _chunks_by_knowledge_point(chunks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for chunk in chunks:
        for knowledge_point_id in chunk.get("knowledge_point_ids", []):
            grouped.setdefault(str(knowledge_point_id), []).append(chunk)
    return grouped


def _first_page_range(evidence: list[dict[str, Any]]) -> dict[str, int | None]:
    for item in evidence:
        page_range = item.get("page_range")
        if isinstance(page_range, dict):
            return {
                "start": page_range.get("start"),
                "end": page_range.get("end"),
            }
    return {"start": None, "end": None}


def _error_patterns(teaching_plan: dict[str, Any]) -> list[dict[str, Any]]:
    misconceptions = teaching_plan.get("misconceptions", [])
    correction_strategies = teaching_plan.get("correction_strategies", [])
    practice_sequence = teaching_plan.get("practice_sequence", [])
    patterns = []
    for index, misconception in enumerate(misconceptions, start=1):
        patterns.append(
            {
                "id": f"misconception-{index}",
                "name": str(misconception),
                "signs": [str(misconception)],
                "correction_strategy": correction_strategies,
                "followup_practice": practice_sequence,
            }
        )
    return patterns


def _selection_keywords(
    knowledge_point: dict[str, Any], teaching_plan: dict[str, Any]
) -> list[str]:
    raw_keywords: list[str] = [
        knowledge_point["id"],
        knowledge_point["name"],
        *knowledge_point.get("mastery_criteria", []),
        *teaching_plan.get("learning_objectives", []),
        *teaching_plan.get("opening", []),
        *teaching_plan.get("diagnosis_questions", []),
        *teaching_plan.get("misconceptions", []),
        *teaching_plan.get("practice_sequence", []),
        *teaching_plan.get("mastery_checks", []),
    ]
    keywords: list[str] = []
    for item in raw_keywords:
        text = str(item).strip()
        if not text:
            continue
        keywords.append(text)
        keywords.extend(_split_chinese_terms(text))
        if re.fullmatch(r"[A-Za-z0-9_/\s-]+", text):
            keywords.extend(part for part in re.split(r"[-_/\\s]+", text) if len(part) >= 3)
    return sorted(dict.fromkeys(keywords), key=lambda value: (len(value), value))


def _split_chinese_terms(text: str) -> list[str]:
    candidates = re.findall(r"[\\u4e00-\\u9fff]{2,}", text)
    terms: list[str] = []
    for candidate in candidates:
        if len(candidate) <= 8:
            terms.append(candidate)
            continue
        for size in (2, 3, 4):
            terms.extend(candidate[index : index + size] for index in range(len(candidate) - size + 1))
    return terms


if __name__ == "__main__":
    main()
