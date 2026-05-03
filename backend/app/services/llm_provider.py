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
    skill_guidance: str
    memory_summary: str
    retrieved_context: str
    core_skill_name: str = ""
    core_skill_guidance: str = ""
    knowledge_skill_name: str = ""
    knowledge_skill_guidance: str = ""

    @property
    def effective_core_skill_name(self) -> str:
        return self.core_skill_name or "OpenTeacher 通用教师核心 Skill"

    @property
    def effective_core_skill_guidance(self) -> str:
        return self.core_skill_guidance or self.skill_guidance

    @property
    def effective_knowledge_skill_name(self) -> str:
        return self.knowledge_skill_name or self.skill_name

    @property
    def effective_knowledge_skill_guidance(self) -> str:
        return self.knowledge_skill_guidance or self.skill_guidance


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

        if any(fragment in normalized for fragment in ["移项不变号", "移项没变号", "+3变成+3"]):
            return (
                "先停在移项这一步。项跨过等号时符号要改变，这是等式两边同时加减同一项的结果。"
                "你先重写这一行：这个项原来在哪一边，移到哪一边，符号应该变成什么？"
            )

        if any(fragment in normalized for fragment in ["-(x", "-（x", "-( x", "负号括号"]):
            return (
                "这里重点看负号括号。把括号前的负号看成 -1，括号里每一项都要乘以 -1。"
                "你先只写出去括号后的式子，不求 x，并说明每一项的符号。"
            )

        if any(word in normalized for word in ["验算", "检验", "代入"]):
            return (
                "很好，现在做代入检验。把你得到的 x 代回原方程，分别算左边和右边。"
                "你先写出代入后的左右两边，我再判断是否相等。"
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
            f"教师核心 Skill：{prompt.effective_core_skill_name}\n"
            f"教师核心规则：\n{prompt.effective_core_skill_guidance}\n"
            f"知识点 Skill：{prompt.effective_knowledge_skill_name}\n"
            f"知识点教学规则：\n{prompt.effective_knowledge_skill_guidance}"
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


class DoubaoChatCompletionsProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        max_tokens: int = 700,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

    def generate_reply(self, prompt: TeacherPrompt) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._build_system_message(prompt)},
                {"role": "user", "content": self._build_user_message(prompt)},
            ],
            "max_tokens": self.max_tokens,
            "temperature": 0.3,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()

        return self._extract_text(response.json())

    def _build_system_message(self, prompt: TeacherPrompt) -> str:
        return (
            "你是 OpenTeacher 的 AI 老师，不是朋友、家长、心理咨询师或答案机器。"
            "你温暖、耐心、严格、有原则，目标是让学生真正学会方法。"
            "禁止直接给可抄写的完整答案；学生没有完成推理前，只能给诊断问题、下一步提示、"
            "或要求学生写出自己的变形步骤。一次只推进一个关键步骤。"
            "如果学生自我否定，先稳定情绪，但必须回到学习任务。"
            "回复必须使用中文，短而清楚。"
            f"当前教师风格：{prompt.teacher_style}。当前 Skill：{prompt.skill_name}。\n"
            f"教师核心 Skill：{prompt.effective_core_skill_name}\n"
            f"教师核心规则：\n{prompt.effective_core_skill_guidance}\n"
            f"知识点 Skill：{prompt.effective_knowledge_skill_name}\n"
            f"知识点教学规则：\n{prompt.effective_knowledge_skill_guidance}"
        )

    def _build_user_message(self, prompt: TeacherPrompt) -> str:
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
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Doubao response did not contain choices")

        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()

        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        chunks.append(text)
            text = "".join(chunks).strip()
            if text:
                return text

        raise ValueError("Doubao response did not contain text output")


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

    if provider in {"doubao", "ark", "volcengine"}:
        api_key = settings.doubao_api_key.get_secret_value() if settings.doubao_api_key else ""
        if api_key and settings.doubao_model:
            return DoubaoChatCompletionsProvider(
                api_key=api_key,
                model=settings.doubao_model,
                base_url=settings.doubao_base_url,
                max_tokens=settings.doubao_max_tokens,
                timeout_seconds=settings.doubao_timeout_seconds,
            )

    return MockTeacherProvider()
