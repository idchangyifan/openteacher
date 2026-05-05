from pathlib import Path

from app.services import rag
from app.services.rag import TextbookFileRagService, get_rag_service


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "textbook-to-skill-sample.yaml"


def test_textbook_file_rag_retrieves_traceable_chunks() -> None:
    service = TextbookFileRagService(FIXTURE_PATH)

    context = service.retrieve("支出 6 元怎么用正数和负数表示？")

    assert "教材 RAG 检索结果" in context
    assert "rag-ch1-kp-positive-negative" in context
    assert "相反意义" in context
    assert "kp-positive-negative-numbers" in context


def test_textbook_file_rag_falls_back_when_query_has_no_match() -> None:
    service = TextbookFileRagService(FIXTURE_PATH, max_chunks=1)

    context = service.retrieve("完全不相关的问题")

    assert "教材 RAG 检索结果" in context
    assert context.count("- [") == 1


def test_get_rag_service_can_select_textbook_file_backend(monkeypatch) -> None:
    monkeypatch.setattr(rag.settings, "rag_backend", "textbook_file")
    monkeypatch.setattr(rag.settings, "textbook_rag_artifact_path", FIXTURE_PATH)

    service = get_rag_service()

    assert isinstance(service, TextbookFileRagService)
    assert "正数和负数" in service.retrieve("正数和负数")


def test_textbook_file_rag_can_feed_teacher_prompt(monkeypatch) -> None:
    captured = {}

    class CapturingProvider:
        def generate_reply(self, prompt):
            captured["retrieved_context"] = prompt.retrieved_context
            return "请先判断“支出”和“收入”是不是相反意义的量。"

    from app.schemas.teacher import StudentContext, TeacherChatRequest
    from app.services.agent_harness import AgentHarness
    from app.services.deepagents_runtime import DeepAgentsTeachingRuntime
    from app.services.lesson_store import InMemoryLessonRepository
    from app.services.memory import MemoryService
    from app.services.planner import PlannerService
    from app.services.skill_registry import SkillRegistry

    repository = InMemoryLessonRepository()
    service = AgentHarness(
        memory_service=MemoryService(),
        rag_service=TextbookFileRagService(FIXTURE_PATH),
        skill_registry=SkillRegistry(),
        llm_provider=CapturingProvider(),
        lesson_repository=repository,
        deepagents_runtime=DeepAgentsTeachingRuntime(
            memory_service=MemoryService(),
            lesson_repository=repository,
        ),
        planner_service=PlannerService(),
    )

    response = service.reply(
        TeacherChatRequest(
            message="支出 6 元怎么用正数和负数表示？",
            context=StudentContext(subject="数学"),
        )
    )

    assert "相反意义" in response.reply
    assert "教材 RAG 检索结果" in captured["retrieved_context"]
    assert "kp-positive-negative-numbers" in captured["retrieved_context"]
