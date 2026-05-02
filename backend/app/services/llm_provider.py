from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.settings import settings


@dataclass(frozen=True)
class TeacherPrompt:
    message: str
    grade: str
    subject: str
    teacher_style: str
    skill_name: str
    memory_summary: str
    retrieved_context: str


class LlmProvider(Protocol):
    def generate_reply(self, prompt: TeacherPrompt) -> str:
        """Generate one teacher reply for a student turn."""


class MockTeacherProvider:
    def generate_reply(self, prompt: TeacherPrompt) -> str:
        normalized = prompt.message.strip()
        style_note = f"我会保持{prompt.teacher_style}，但不会替你抄答案。"

        if any(word in normalized for word in ["答案", "直接告诉", "抄"]):
            return (
                f"不行。我是老师，不是答案机器。{style_note}你先写出下一步，我会检查你的推理。"
                "如果你写错，我会指出具体错在哪里。"
            )

        if "x" in normalized or "(" in normalized or "（" in normalized:
            return (
                f"我会按「{prompt.skill_name}」来教。先停在第一步，不要跳答案。"
                "请你写出去括号后的式子，并说明每一项的符号为什么这样变。"
                f"我记得你的学习重点是：{prompt.memory_summary}。{style_note}"
            )

        if any(word in normalized for word in ["笨", "学不会", "不会", "太难"]):
            return (
                "先别给自己下结论。我们按老师的方式处理：你告诉我卡在读题、列式、"
                "去括号、移项、合并同类项，还是验算？只回答一个也可以。"
            )

        return (
            f"收到。当前是{prompt.grade}{prompt.subject}场景。请补充题目原文和你已经写到的步骤。"
            f"我会结合{prompt.retrieved_context}来判断你的卡点。"
        )


class OpenAIResponsesProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        max_output_tokens: int = 700,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_output_tokens = max_output_tokens
        self.timeout_seconds = timeout_seconds

    def generate_reply(self, prompt: TeacherPrompt) -> str:
        payload = {
            "model": self.model,
            "instructions": self._build_instructions(prompt),
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": self._build_input(prompt),
                        }
                    ],
                }
            ],
            "max_output_tokens": self.max_output_tokens,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{self.base_url}/responses", headers=headers, json=payload)
            response.raise_for_status()

        return self._extract_text(response.json())

    def _build_instructions(self, prompt: TeacherPrompt) -> str:
        return (
            "你是 OpenTeacher 的 AI 老师，不是聊天朋友、家长、心理咨询师或答案机器。"
            "你要温暖、耐心、严格、讲原则。你的目标是让学生真正学会方法。"
            "不要直接给可抄写的完整答案；除非学生已经完成推理，否则只给下一步提示、"
            "诊断问题或要求学生写出自己的步骤。学生自我否定时要稳定情绪，但仍回到学习任务。"
            f"当前教师风格：{prompt.teacher_style}。当前 Skill：{prompt.skill_name}。"
            "回复必须使用中文，短而清楚，一次只推进一个关键步骤。"
        )

    def _build_input(self, prompt: TeacherPrompt) -> str:
        return "\n".join(
            [
                f"年级：{prompt.grade}",
                f"科目：{prompt.subject}",
                f"学生记忆摘要：{prompt.memory_summary}",
                f"检索到的教学上下文：{prompt.retrieved_context}",
                f"学生消息：{prompt.message}",
            ]
        )

    def _extract_text(self, payload: dict) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        chunks: list[str] = []
        for item in payload.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str):
                    chunks.append(text)

        text = "".join(chunks).strip()
        if not text:
            raise ValueError("LLM response did not contain text output")

        return text


def get_llm_provider() -> LlmProvider:
    provider = settings.llm_provider.strip().lower()

    if provider == "openai":
        api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        if api_key and settings.openai_model:
            return OpenAIResponsesProvider(
                api_key=api_key,
                model=settings.openai_model,
                base_url=settings.openai_base_url,
                max_output_tokens=settings.openai_max_output_tokens,
                timeout_seconds=settings.openai_timeout_seconds,
            )

    return MockTeacherProvider()
