from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.lesson import LessonSessionDetail, LessonSessionSummary


@dataclass(frozen=True)
class LearningEvent:
    kind: str
    summary: str


class MemoryService:
    """Boundary for student memory storage.

    The first version is intentionally in-memory/mock-like. Long-term memory should
    move behind this boundary into MongoDB-backed lesson history, structured memory
    cards, extraction jobs, and vector search. Do not bind student long-term memory
    to PostgreSQL tables.
    """

    def get_student_summary(
        self,
        student_id: str,
        subject: str = "",
        lesson_detail: "LessonSessionDetail | None" = None,
        recent_lessons: "list[LessonSessionSummary] | None" = None,
    ) -> str:
        memory_parts: list[str] = []
        if lesson_detail is not None:
            session = lesson_detail.session
            memory_parts.extend(
                [
                    "当前课堂优先",
                    f"课堂：{session.title}",
                    f"目标：{session.lesson_goal}",
                    f"科目：{session.grade}{session.subject}",
                    f"当前 skill：{session.current_skill_id or '未设置'}",
                    f"当前知识点：{session.current_knowledge_point_id or '未设置'}",
                    f"课堂摘要：{session.summary}",
                ]
            )
            last_teacher_message = next(
                (
                    message.content
                    for message in reversed(lesson_detail.messages)
                    if message.role == "teacher"
                ),
                "",
            )
            if last_teacher_message:
                memory_parts.append(f"最近老师引导：{last_teacher_message}")

        if recent_lessons:
            formatted_recent_lessons = []
            current_session_id = (
                lesson_detail.session.id if lesson_detail is not None else None
            )
            for lesson in recent_lessons[:3]:
                if lesson.id == current_session_id:
                    continue
                formatted_recent_lessons.append(
                    (
                        f"{lesson.grade}{lesson.subject}《{lesson.title}》"
                        f" skill={lesson.current_skill_id or '未设置'}"
                        f" 知识点={lesson.current_knowledge_point_id or '未设置'}"
                        f" 摘要={lesson.summary}"
                    )
                )
            if formatted_recent_lessons:
                memory_parts.append("最近课堂：" + " | ".join(formatted_recent_lessons))

        if memory_parts:
            memory_parts.append("优先级：当前课堂记录 > 当前课堂状态 > 最近课堂 > 长期背景假设。")
            return "；".join(memory_parts)

        subject_note = f"{subject}学习" if subject else "当前学习"
        return f"暂无可靠长期记忆；优先依据当前课堂记录和学生本轮输入来判断{subject_note}。"

    def format_deepagents_memory(
        self,
        *,
        student_id: str,
        subject: str,
        lesson_detail: "LessonSessionDetail | None" = None,
        recent_lessons: "list[LessonSessionSummary] | None" = None,
    ) -> str:
        summary = self.get_student_summary(
            student_id,
            subject=subject,
            lesson_detail=lesson_detail,
            recent_lessons=recent_lessons,
        )
        return "\n".join(
            [
                "# OpenTeacher Student Memory",
                "",
                f"student_id: {student_id}",
                f"subject: {subject or 'unknown'}",
                "",
                "## Memory Priority",
                "",
                "- Current lesson transcript and lesson state are authoritative.",
                "- Long-term memory is background only; never override current_skill_id.",
                "- If current and long-term memory conflict, trust the current lesson.",
                "",
                "## Memory Summary",
                "",
                summary,
            ]
        )

    def record_learning_event(
        self,
        student_id: str,
        subject: str,
        message: str,
        reply: str,
    ) -> LearningEvent:
        if any(word in message for word in ["答案", "直接告诉", "抄"]):
            return LearningEvent(kind="learning_behavior", summary="学生尝试直接获取答案")

        if "x" in message:
            return LearningEvent(kind="academic_signal", summary="学生正在练习一元一次方程")

        return LearningEvent(kind="conversation", summary=f"学生进行了{subject}学习对话")


def get_memory_service() -> MemoryService:
    return MemoryService()
