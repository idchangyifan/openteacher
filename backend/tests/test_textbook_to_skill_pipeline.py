from pathlib import Path

import yaml

from app.services.textbook_to_skill_pipeline import (
    PipelineInputError,
    apply_outline_to_pipeline_source,
    build_textbook_to_skill_artifact,
)

INPUT_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "textbook-to-skill-input.yaml"
OUTLINE_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "textbook-outline-sample.yaml"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "textbook-to-skill-sample.yaml"


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert isinstance(data, dict)
    return data


def test_textbook_to_skill_sample_has_core_pipeline_outputs() -> None:
    data = load_yaml(FIXTURE_PATH)

    for key in [
        "input_sources",
        "textbook_manifest",
        "course_map",
        "knowledge_point_graph",
        "skill_drafts",
        "rag_chunks",
        "eval_cases",
        "review_record",
    ]:
        assert key in data


def test_textbook_to_skill_sample_separates_textbook_and_llm_sources() -> None:
    data = load_yaml(FIXTURE_PATH)
    source_types = {source["source_type"] for source in data["input_sources"]}

    assert "textbook_pdf" in source_types
    assert "llm_inferred" in source_types
    assert data["textbook_manifest"]["copyright_policy"] == "authorized_use"


def test_textbook_to_skill_sample_marks_generated_assets_as_draft() -> None:
    data = load_yaml(FIXTURE_PATH)

    assert data["review_record"]["status"] == "draft"
    assert all(draft["review_status"] == "draft" for draft in data["skill_drafts"])
    assert all(chunk["review_status"] == "draft" for chunk in data["rag_chunks"])


def test_textbook_to_skill_sample_rag_chunks_are_traceable() -> None:
    data = load_yaml(FIXTURE_PATH)
    knowledge_point_ids = {item["id"] for item in data["knowledge_point_graph"]}

    for chunk in data["rag_chunks"]:
        assert chunk["id"]
        assert chunk["source_ref"]
        assert chunk["chapter_id"]
        assert chunk["text"]
        assert chunk["copyright_policy"] in {
            "generated_review_required",
            "local_research_only",
            "do_not_publish_textbook_content",
            "authorized_use",
        }
        assert set(chunk["knowledge_point_ids"]).issubset(knowledge_point_ids)


def test_textbook_to_skill_builder_generates_expected_artifact_shape() -> None:
    source = load_yaml(INPUT_FIXTURE_PATH)

    artifact = build_textbook_to_skill_artifact(source)

    assert artifact["pipeline_id"] == "opent-pipeline-rj-junior-math-grade7-vol1-chapter1"
    assert artifact["textbook_manifest"]["textbook_id"] == "rj-junior-math-grade7-vol1"
    assert artifact["course_map"]["chapters"][0]["sections"][0]["title"] == "正数和负数"
    assert artifact["skill_drafts"][0]["review_status"] == "draft"
    assert artifact["rag_chunks"][0]["source_ref"] == "llm-draft-teaching-design"
    assert artifact["eval_cases"][0]["id"] == "eval-positive-negative-answer-seeking"


def test_textbook_to_skill_builder_can_apply_pdf_outline_page_ranges() -> None:
    source = load_yaml(INPUT_FIXTURE_PATH)
    outline = load_yaml(OUTLINE_FIXTURE_PATH)

    merged_source = apply_outline_to_pipeline_source(source, outline)
    artifact = build_textbook_to_skill_artifact(merged_source)

    chapter = artifact["course_map"]["chapters"][0]
    sections = {section["id"]: section for section in chapter["sections"]}

    assert artifact["textbook_manifest"]["copyright_policy"] == "authorized_use"
    assert artifact["textbook_manifest"]["parse_status"] == "pdf_outline_candidate"
    assert chapter["page_range"] == {"start": 6, "end": 17}
    assert sections["ch1-sec1"]["page_range"] == {"start": 6, "end": 7}
    assert sections["ch1-sec2"]["page_range"] == {"start": 8, "end": 13}


def test_textbook_to_skill_builder_rejects_unknown_chunk_knowledge_point() -> None:
    source = load_yaml(INPUT_FIXTURE_PATH)
    source["teaching_designs"][0]["rag_chunks"][0]["knowledge_point_ids"] = ["missing-kp"]

    try:
        build_textbook_to_skill_artifact(source)
    except PipelineInputError as exc:
        assert "unknown knowledge points" in str(exc)
    else:
        raise AssertionError("Expected PipelineInputError")
