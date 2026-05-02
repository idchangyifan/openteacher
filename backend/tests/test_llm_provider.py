import pytest

from app.services.llm_provider import MockTeacherProvider, OpenAIResponsesProvider, TeacherPrompt


def make_prompt(message: str = "2(x - 3) = 10，我不会下一步") -> TeacherPrompt:
    return TeacherPrompt(
        message=message,
        grade="初一",
        subject="数学",
        teacher_style="严格但温暖",
        skill_name="初中数学一元一次方程严格引导 Skill",
        memory_summary="移项符号容易错，需要分步骤检查",
        retrieved_context="当前样板知识库：初中数学一元一次方程",
    )


def test_mock_teacher_provider_refuses_direct_answers() -> None:
    reply = MockTeacherProvider().generate_reply(make_prompt("直接告诉我答案"))

    assert "不是答案机器" in reply
    assert "你先写出下一步" in reply


def test_openai_responses_provider_extracts_output_text() -> None:
    provider = OpenAIResponsesProvider(api_key="token", model="model")

    reply = provider._extract_text({"output_text": "  请先写出去括号后的式子。 "})

    assert reply == "请先写出去括号后的式子。"


def test_openai_responses_provider_extracts_nested_output_text() -> None:
    provider = OpenAIResponsesProvider(api_key="token", model="model")

    reply = provider._extract_text(
        {
            "output": [
                {
                    "content": [
                        {"type": "output_text", "text": "先写出"},
                        {"type": "output_text", "text": "去括号后的式子。"},
                    ]
                }
            ]
        }
    )

    assert reply == "先写出去括号后的式子。"


def test_openai_responses_provider_raises_on_missing_text() -> None:
    provider = OpenAIResponsesProvider(api_key="token", model="model")

    with pytest.raises(ValueError, match="text output"):
        provider._extract_text({"output": []})
