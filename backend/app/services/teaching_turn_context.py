from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class StudentAnswerEvaluation:
    status: str
    feedback: str


def format_message_lines(messages: Iterable[Any]) -> list[str]:
    return [
        f"{_message_role(message)}: {_message_content(message)}"
        for message in messages
    ]


def infer_current_question(messages: Iterable[Any]) -> str | None:
    for message in reversed(list(messages)):
        content = _message_content(message)
        if _message_role(message) == "teacher" and any(mark in content for mark in ["？", "?"]):
            return content
    return None


def evaluate_student_answer(question: str | None, answer: str) -> StudentAnswerEvaluation:
    normalized_question = normalize_text(question or "")
    compact_answer = normalize_answer(answer)
    if not question:
        if _is_stuck_answer(compact_answer):
            return StudentAnswerEvaluation("stuck", "学生表达卡住。")
        return StudentAnswerEvaluation("needs_evaluation", "")

    if _is_income_expense_question(normalized_question):
        if compact_answer in {"-6", "-6元"}:
            return StudentAnswerEvaluation(
                "correct",
                "学生回答 -6 正确。先确认正确，再追问一句：为什么这里要用负号？不要切到下一题。",
            )
        if compact_answer in {"*6", "×6", "x6"}:
            return StudentAnswerEvaluation(
                "incorrect_symbol",
                "学生把符号写成了乘号。指出 * 不是正负号；继续让学生判断支出应该用 + 还是 -，不要直接说出完整答案，也不要切到下一题。",
            )
        if compact_answer in {"&6", "与6", "和6"}:
            return StudentAnswerEvaluation(
                "invalid_symbol",
                "学生写了“与/和”一类连接符，不是正负号。停留在当前题，只问：支出和收入方向相反时，应该用 + 还是 -？不要重启课堂。",
            )
        if compact_answer in {"+6", "+6元", "6", "6元"}:
            return StudentAnswerEvaluation(
                "incorrect_sign",
                "学生没有表示出支出和收入的相反意义。只提示收入用 +，支出要用相反符号；不要切到下一题。",
            )
        if _is_stuck_answer(compact_answer):
            return StudentAnswerEvaluation(
                "stuck",
                "学生卡住了。用收入和支出是相反意义的量来提示，并让学生继续回答这同一道题。",
            )

    if _is_stuck_answer(compact_answer):
        return StudentAnswerEvaluation("stuck", "学生表达卡住。")
    return StudentAnswerEvaluation("needs_evaluation", "")


def normalize_text(value: str) -> str:
    return (
        value.replace(" ", "")
        .replace("＋", "+")
        .replace("－", "-")
        .replace("，", ",")
        .replace("？", "?")
    )


def normalize_answer(value: str) -> str:
    compact = normalize_text(value.strip().lower())
    compact = compact.replace("啊", "").replace("呀", "").replace("呢", "")
    compact = compact.replace("负六", "-6").replace("负6", "-6").replace("减6", "-6")
    compact = compact.replace("乘6", "*6")
    return compact


def _is_income_expense_question(normalized_question: str) -> bool:
    return (
        "收入10" in normalized_question
        and "支出6" in normalized_question
        or (
            "支出" in normalized_question
            and "收入" in normalized_question
            and "+还是-" in normalized_question
        )
    )


def _is_stuck_answer(compact_answer: str) -> bool:
    return any(word in compact_answer for word in ["不知道", "不会", "不懂", "卡住"])


def _message_role(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("role") or "")
    return str(getattr(message, "role", ""))


def _message_content(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(getattr(message, "content", ""))
