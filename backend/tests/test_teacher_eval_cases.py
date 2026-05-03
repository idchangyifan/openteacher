from pathlib import Path

import yaml


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "teacher-core-golden.yaml"


def load_cases() -> dict:
    payload = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_teacher_core_golden_cases_have_required_structure() -> None:
    payload = load_cases()
    cases = payload.get("cases")

    assert isinstance(cases, list)
    assert len(cases) >= 10

    required_fields = {
        "id",
        "subject",
        "grade",
        "knowledge_point",
        "learner_state",
        "student_message",
        "expected_behaviors",
        "forbidden_behaviors",
        "ideal_teacher_move",
        "scoring_notes",
    }
    case_ids: set[str] = set()
    for case in cases:
        assert isinstance(case, dict)
        assert required_fields <= case.keys()
        assert case["id"] not in case_ids
        case_ids.add(case["id"])
        assert isinstance(case["expected_behaviors"], list)
        assert isinstance(case["forbidden_behaviors"], list)
        assert len(case["expected_behaviors"]) >= 2
        assert len(case["forbidden_behaviors"]) >= 2
        assert str(case["student_message"]).strip()
        assert str(case["ideal_teacher_move"]).strip()


def test_teacher_core_golden_cases_cover_cross_knowledge_behavior() -> None:
    payload = load_cases()
    cases = payload["cases"]

    subjects = {case["subject"] for case in cases}
    learner_states = {case["learner_state"] for case in cases}
    knowledge_points = {case["knowledge_point"] for case in cases}

    assert {"math", "chinese", "english", "physics"} <= subjects
    assert len(knowledge_points) >= 8
    assert {
        "insufficient_information",
        "answer_seeking",
        "genuinely_stuck",
        "concept_error",
        "step_error",
        "emotional_distress",
        "safety_risk",
    } <= learner_states


def test_teacher_core_golden_cases_include_core_boundaries() -> None:
    payload = load_cases()
    cases = payload["cases"]
    forbidden_text = "\n".join(
        behavior for case in cases for behavior in case["forbidden_behaviors"]
    )
    expected_text = "\n".join(
        behavior for case in cases for behavior in case["expected_behaviors"]
    )

    assert "copyable" in forbidden_text
    assert "exact address" in forbidden_text
    assert "identity" in forbidden_text
    assert "trusted adult" in expected_text
    assert "Ask for" in expected_text
