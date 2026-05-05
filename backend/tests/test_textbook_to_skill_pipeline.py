from pathlib import Path

import yaml


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "textbook-to-skill-sample.yaml"


def load_fixture() -> dict:
    with FIXTURE_PATH.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert isinstance(data, dict)
    return data


def test_textbook_to_skill_sample_has_core_pipeline_outputs() -> None:
    data = load_fixture()

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
    data = load_fixture()
    source_types = {source["source_type"] for source in data["input_sources"]}

    assert "textbook_pdf" in source_types
    assert "llm_inferred" in source_types
    assert data["textbook_manifest"]["copyright_policy"] == "do_not_publish_textbook_content"


def test_textbook_to_skill_sample_marks_generated_assets_as_draft() -> None:
    data = load_fixture()

    assert data["review_record"]["status"] == "draft"
    assert all(draft["review_status"] == "draft" for draft in data["skill_drafts"])
    assert all(chunk["review_status"] == "draft" for chunk in data["rag_chunks"])


def test_textbook_to_skill_sample_rag_chunks_are_traceable() -> None:
    data = load_fixture()
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
        }
        assert set(chunk["knowledge_point_ids"]).issubset(knowledge_point_ids)
