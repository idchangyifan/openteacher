import pytest

from app.services.llm_provider import (
    DoubaoChatCompletionsProvider,
    MockTeacherProvider,
    OpenAIResponsesProvider,
    TeacherPrompt,
)


def make_prompt(message: str = "2(x - 3) = 10，我不会下一步") -> TeacherPrompt:
    return TeacherPrompt(
        message=message,
        grade="初一",
        subject="数学",
        teacher_style="严格但温暖",
        skill_name="Universal Teacher Core + 初中数学一元一次方程严格引导 Skill",
        skill_guidance="教师核心规则 + 知识点规则",
        memory_summary="移项符号容易错，需要分步骤检查",
        retrieved_context="当前样板知识库：初中数学一元一次方程",
        core_skill_name="Universal Teacher Core",
        core_skill_guidance="不要给可抄写完整答案；要求学生表达当前步骤。",
        knowledge_skill_name="初中数学一元一次方程严格引导 Skill",
        knowledge_skill_guidance="移项要检查变号；最后代入检验。",
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


def test_doubao_chat_completions_provider_extracts_reply_text() -> None:
    provider = DoubaoChatCompletionsProvider(api_key="token", model="model")

    reply = provider._extract_text(
        {"choices": [{"message": {"role": "assistant", "content": "  先写出去括号后的式子。 "}}]}
    )

    assert reply == "先写出去括号后的式子。"


def test_doubao_chat_completions_provider_raises_on_missing_text() -> None:
    provider = DoubaoChatCompletionsProvider(api_key="token", model="model")

    with pytest.raises(ValueError, match="text output"):
        provider._extract_text({"choices": [{"message": {"content": ""}}]})


def test_doubao_chat_completions_provider_system_message_contains_skill_guidance() -> None:
    provider = DoubaoChatCompletionsProvider(api_key="token", model="model")

    system_message = provider._build_system_message(make_prompt())

    assert "不是朋友" in system_message
    assert "Universal Teacher Core" in system_message
    assert "不要给可抄写完整答案" in system_message
    assert "移项要检查变号" in system_message
    assert "先明确确认正确" in system_message
