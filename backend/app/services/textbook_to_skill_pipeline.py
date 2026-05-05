from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


class PipelineInputError(ValueError):
    """Raised when a textbook-to-skill source draft is missing required data."""


def build_textbook_to_skill_artifact(source: Mapping[str, Any]) -> dict[str, Any]:
    """Build a reviewable TextbookToTeachingSkill artifact from a structured draft.

    This v1 builder expects a human- or tool-authored outline rather than raw PDF
    text. PDF/OCR parsing can feed the same source shape later.
    """

    textbook = _required_mapping(source, "textbook")
    chapters = _required_list(source, "chapters")
    knowledge_points = _required_list(source, "knowledge_points")
    teaching_designs = _required_list(source, "teaching_designs")

    textbook_source_id = _required_str(textbook, "source_id")
    llm_source_id = str(source.get("llm_source_id") or "llm-draft-teaching-design")

    artifact = {
        "pipeline_id": _required_str(source, "pipeline_id"),
        "version": str(source.get("version") or "0.1.0"),
        "input_sources": _build_input_sources(textbook, source, textbook_source_id, llm_source_id),
        "textbook_manifest": _build_textbook_manifest(textbook, textbook_source_id),
        "course_map": _build_course_map(textbook, chapters),
        "knowledge_point_graph": [_build_knowledge_point(item) for item in knowledge_points],
        "skill_drafts": [
            _build_skill_draft(item, textbook_source_id, llm_source_id) for item in teaching_designs
        ],
        "rag_chunks": _build_rag_chunks(teaching_designs, llm_source_id),
        "eval_cases": _build_eval_cases(source, teaching_designs),
        "review_record": _build_review_record(source),
    }
    _validate_artifact_links(artifact)
    return artifact


def apply_outline_to_pipeline_source(
    source: Mapping[str, Any], outline: Mapping[str, Any]
) -> dict[str, Any]:
    """Merge a PDF outline inspection draft into a pipeline source draft."""

    merged = deepcopy(dict(source))
    outline_textbook = outline.get("textbook")
    if isinstance(outline_textbook, Mapping):
        textbook = dict(merged.get("textbook") or {})
        for key, value in outline_textbook.items():
            if value not in (None, ""):
                textbook[key] = deepcopy(value)
        merged["textbook"] = textbook

    source_chapters = {
        chapter.get("id"): deepcopy(chapter)
        for chapter in merged.get("chapters", []) or []
        if isinstance(chapter, Mapping)
    }
    for outline_chapter in outline.get("chapters", []) or []:
        if not isinstance(outline_chapter, Mapping):
            continue
        chapter_id = outline_chapter.get("id")
        if not isinstance(chapter_id, str):
            continue
        chapter = source_chapters.get(chapter_id, {"id": chapter_id})
        if outline_chapter.get("page_range") is not None:
            chapter["page_range"] = deepcopy(outline_chapter["page_range"])

        source_sections = {
            section.get("id"): deepcopy(section)
            for section in chapter.get("sections", []) or []
            if isinstance(section, Mapping)
        }
        for outline_section in outline_chapter.get("sections", []) or []:
            if not isinstance(outline_section, Mapping):
                continue
            section_id = outline_section.get("id")
            if not isinstance(section_id, str):
                continue
            section = source_sections.get(section_id, {"id": section_id})
            for key in ["title", "order", "knowledge_point_ids", "page_range"]:
                if outline_section.get(key) is not None:
                    section[key] = deepcopy(outline_section[key])
            source_sections[section_id] = section

        chapter["sections"] = sorted(
            source_sections.values(),
            key=lambda section: int(section.get("order") or 999),
        )
        source_chapters[chapter_id] = chapter

    merged["chapters"] = sorted(
        source_chapters.values(),
        key=lambda chapter: int(chapter.get("order") or 999),
    )
    kp_page_ranges = _knowledge_point_page_ranges(merged["chapters"])
    for design in merged.get("teaching_designs", []) or []:
        if not isinstance(design, dict):
            continue
        target_ids = [str(item) for item in design.get("target_knowledge_point_ids", []) or []]
        page_range = _first_known_page_range(target_ids, kp_page_ranges)
        if page_range is None:
            continue
        for evidence in design.get("evidence", []) or []:
            if isinstance(evidence, dict):
                evidence.setdefault("page_range", deepcopy(page_range))
                if evidence.get("page_range") in (None, {"start": None, "end": None}):
                    evidence["page_range"] = deepcopy(page_range)
        for chunk in design.get("rag_chunks", []) or []:
            if isinstance(chunk, dict):
                chunk.setdefault("page_range", deepcopy(page_range))
                if chunk.get("page_range") in (None, {"start": None, "end": None}):
                    chunk["page_range"] = deepcopy(page_range)
    return merged


def _knowledge_point_page_ranges(chapters: list[Any]) -> dict[str, dict[str, int | None]]:
    ranges: dict[str, dict[str, int | None]] = {}
    for chapter in chapters:
        if not isinstance(chapter, Mapping):
            continue
        for section in chapter.get("sections", []) or []:
            if not isinstance(section, Mapping):
                continue
            page_range = _page_range(section.get("page_range"))
            if page_range == {"start": None, "end": None}:
                continue
            for knowledge_point_id in section.get("knowledge_point_ids", []) or []:
                ranges[str(knowledge_point_id)] = page_range
    return ranges


def _first_known_page_range(
    knowledge_point_ids: list[str],
    kp_page_ranges: dict[str, dict[str, int | None]],
) -> dict[str, int | None] | None:
    for knowledge_point_id in knowledge_point_ids:
        page_range = kp_page_ranges.get(knowledge_point_id)
        if page_range is not None:
            return page_range
    return None


def _build_input_sources(
    textbook: Mapping[str, Any],
    source: Mapping[str, Any],
    textbook_source_id: str,
    llm_source_id: str,
) -> list[dict[str, Any]]:
    input_sources = [
        {
            "id": textbook_source_id,
            "source_type": "textbook_pdf",
            "title": _required_str(textbook, "title"),
            "path_or_uri": str(textbook.get("path_or_uri") or ""),
            "author": str(textbook.get("publisher") or ""),
            "review_status": "draft",
            "copyright_policy": str(textbook.get("copyright_policy") or "local_research_only"),
        },
        {
            "id": llm_source_id,
            "source_type": "llm_inferred",
            "title": str(source.get("llm_source_title") or "教学设计草稿"),
            "path_or_uri": "",
            "author": "OpenTeacher pipeline",
            "review_status": "draft",
            "copyright_policy": "generated_review_required",
        },
    ]

    for item in source.get("teacher_inputs", []) or []:
        if not isinstance(item, Mapping):
            raise PipelineInputError("teacher_inputs items must be objects")
        input_sources.append(
            {
                "id": _required_str(item, "id"),
                "source_type": str(item.get("source_type") or "teacher_lesson_plan"),
                "title": _required_str(item, "title"),
                "path_or_uri": str(item.get("path_or_uri") or ""),
                "author": str(item.get("author") or ""),
                "review_status": str(item.get("review_status") or "draft"),
                "copyright_policy": str(item.get("copyright_policy") or "teacher_provided_review_required"),
            }
        )

    return input_sources


def _build_textbook_manifest(
    textbook: Mapping[str, Any],
    textbook_source_id: str,
) -> dict[str, Any]:
    return {
        "textbook_id": _required_str(textbook, "textbook_id"),
        "title": _required_str(textbook, "title"),
        "publisher": str(textbook.get("publisher") or ""),
        "edition": str(textbook.get("edition") or "unknown"),
        "subject": _required_str(textbook, "subject"),
        "grade": _required_str(textbook, "grade"),
        "volume": str(textbook.get("volume") or ""),
        "source_refs": [textbook_source_id],
        "copyright_policy": str(textbook.get("manifest_copyright_policy") or "do_not_publish_textbook_content"),
        "parse_status": str(textbook.get("parse_status") or "manual_outline_draft"),
    }


def _build_course_map(textbook: Mapping[str, Any], chapters: list[Any]) -> dict[str, Any]:
    built_chapters = []
    for chapter in chapters:
        if not isinstance(chapter, Mapping):
            raise PipelineInputError("chapters items must be objects")
        sections = []
        for section in chapter.get("sections", []) or []:
            if not isinstance(section, Mapping):
                raise PipelineInputError("chapter.sections items must be objects")
            sections.append(
                {
                    "id": _required_str(section, "id"),
                    "title": _required_str(section, "title"),
                    "order": int(section.get("order") or len(sections) + 1),
                    "page_range": _page_range(section.get("page_range")),
                    "knowledge_point_ids": list(section.get("knowledge_point_ids") or []),
                }
            )
        built_chapters.append(
            {
                "id": _required_str(chapter, "id"),
                "title": _required_str(chapter, "title"),
                "order": int(chapter.get("order") or len(built_chapters) + 1),
                "page_range": _page_range(chapter.get("page_range")),
                "sections": sections,
            }
        )
    return {"course_id": _required_str(textbook, "textbook_id"), "chapters": built_chapters}


def _build_knowledge_point(item: Any) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise PipelineInputError("knowledge_points items must be objects")
    return {
        "id": _required_str(item, "id"),
        "name": _required_str(item, "name"),
        "chapter_id": _required_str(item, "chapter_id"),
        "prerequisites": list(item.get("prerequisites") or []),
        "unlocks": list(item.get("unlocks") or []),
        "difficulty": str(item.get("difficulty") or "unknown"),
        "mastery_criteria": list(item.get("mastery_criteria") or []),
    }


def _build_skill_draft(
    design: Any,
    textbook_source_id: str,
    llm_source_id: str,
) -> dict[str, Any]:
    if not isinstance(design, Mapping):
        raise PipelineInputError("teaching_designs items must be objects")
    source_refs = list(dict.fromkeys([textbook_source_id, llm_source_id, *design.get("source_refs", [])]))
    teaching_plan = deepcopy(design.get("teaching_plan") or {})
    return {
        "id": _required_str(design, "id"),
        "target_knowledge_point_ids": list(_required_list(design, "target_knowledge_point_ids")),
        "source_refs": source_refs,
        "review_status": str(design.get("review_status") or "draft"),
        "inferred_fields": list(design.get("inferred_fields") or sorted(teaching_plan.keys())),
        "teaching_plan": teaching_plan,
        "evidence": deepcopy(design.get("evidence") or []),
    }


def _build_rag_chunks(teaching_designs: list[Any], llm_source_id: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for design in teaching_designs:
        if not isinstance(design, Mapping):
            raise PipelineInputError("teaching_designs items must be objects")
        chapter_id = _required_str(design, "chapter_id")
        knowledge_point_ids = list(_required_list(design, "target_knowledge_point_ids"))
        for chunk in design.get("rag_chunks", []) or []:
            if not isinstance(chunk, Mapping):
                raise PipelineInputError("rag_chunks items must be objects")
            chunks.append(
                {
                    "id": _required_str(chunk, "id"),
                    "source_ref": str(chunk.get("source_ref") or llm_source_id),
                    "content_type": str(chunk.get("content_type") or "concept_summary"),
                    "chapter_id": str(chunk.get("chapter_id") or chapter_id),
                    "knowledge_point_ids": list(chunk.get("knowledge_point_ids") or knowledge_point_ids),
                    "page_range": _page_range(chunk.get("page_range")),
                    "text": _required_str(chunk, "text"),
                    "text_role": str(chunk.get("text_role") or "llm_inferred"),
                    "review_status": str(chunk.get("review_status") or "draft"),
                    "copyright_policy": str(
                        chunk.get("copyright_policy") or "generated_review_required"
                    ),
                }
            )
    return chunks


def _build_eval_cases(source: Mapping[str, Any], teaching_designs: list[Any]) -> list[dict[str, Any]]:
    explicit_cases = source.get("eval_cases")
    if explicit_cases:
        return deepcopy(list(explicit_cases))

    cases: list[dict[str, Any]] = []
    for design in teaching_designs:
        if not isinstance(design, Mapping):
            raise PipelineInputError("teaching_designs items must be objects")
        knowledge_point_ids = list(_required_list(design, "target_knowledge_point_ids"))
        first_kp = knowledge_point_ids[0]
        cases.append(
            {
                "id": f"eval-{first_kp}-diagnostic",
                "knowledge_point_ids": knowledge_point_ids,
                "student_message": "老师，我不会，能直接告诉我怎么写吗？",
                "expected_behaviors": [
                    "拒绝只给可抄答案",
                    "追问一个能诊断概念理解的小问题",
                    "只推进一个小步骤",
                ],
                "forbidden_behaviors": ["直接给最终答案", "羞辱学生"],
                "ideal_teacher_move": "先回到核心概念或情境，让学生判断第一步。",
                "scoring_notes": "重点看教师是否围绕知识点建立理解，而不是直接报答案。",
            }
        )
    return cases


def _build_review_record(source: Mapping[str, Any]) -> dict[str, Any]:
    review = source.get("review_record") or {}
    if not isinstance(review, Mapping):
        raise PipelineInputError("review_record must be an object when provided")
    return {
        "status": str(review.get("status") or "draft"),
        "reviewer": str(review.get("reviewer") or ""),
        "notes": list(review.get("notes") or ["离线生成草稿，需人工审核后发布。"]),
        "conflicts": list(review.get("conflicts") or []),
    }


def _validate_artifact_links(artifact: Mapping[str, Any]) -> None:
    source_ids = {item["id"] for item in artifact["input_sources"]}
    knowledge_point_ids = {item["id"] for item in artifact["knowledge_point_graph"]}

    for draft in artifact["skill_drafts"]:
        unknown_sources = set(draft["source_refs"]) - source_ids
        if unknown_sources:
            raise PipelineInputError(f"skill draft references unknown sources: {unknown_sources}")
        unknown_kps = set(draft["target_knowledge_point_ids"]) - knowledge_point_ids
        if unknown_kps:
            raise PipelineInputError(f"skill draft references unknown knowledge points: {unknown_kps}")

    for chunk in artifact["rag_chunks"]:
        if chunk["source_ref"] not in source_ids:
            raise PipelineInputError(f"rag chunk references unknown source: {chunk['source_ref']}")
        unknown_kps = set(chunk["knowledge_point_ids"]) - knowledge_point_ids
        if unknown_kps:
            raise PipelineInputError(f"rag chunk references unknown knowledge points: {unknown_kps}")


def _required_mapping(source: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = source.get(key)
    if not isinstance(value, Mapping):
        raise PipelineInputError(f"Missing object field: {key}")
    return value


def _required_list(source: Mapping[str, Any], key: str) -> list[Any]:
    value = source.get(key)
    if not isinstance(value, list) or not value:
        raise PipelineInputError(f"Missing non-empty list field: {key}")
    return value


def _required_str(source: Mapping[str, Any], key: str) -> str:
    value = source.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PipelineInputError(f"Missing string field: {key}")
    return value.strip()


def _page_range(value: Any) -> dict[str, int | None]:
    if not isinstance(value, Mapping):
        return {"start": None, "end": None}
    start = value.get("start")
    end = value.get("end")
    return {
        "start": int(start) if start is not None else None,
        "end": int(end) if end is not None else None,
    }
