from pathlib import Path

from app.services import rag
from app.services.rag import (
    MongoTextbookRagService,
    RagService,
    RagTurnContext,
    TextbookFileRagService,
    get_rag_service,
)


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


class FakeCursor(list):
    def limit(self, _count: int):
        return self


class FakeTextbookChunksCollection:
    def __init__(self, docs):
        self.docs = docs
        self.last_filter = None
        self.filters = []

    def find(self, filter_doc, _projection):
        self.last_filter = filter_doc
        self.filters.append(filter_doc)
        return FakeCursor(self.docs)


def test_mongo_textbook_rag_retrieves_imported_chunks() -> None:
    collection = FakeTextbookChunksCollection(
        [
            {
                "id": "rag-ch1-kp-positive-negative-summary",
                "source_ref": "llm-draft-teaching-design",
                "content_type": "concept_summary",
                "chapter_id": "ch1",
                "knowledge_point_ids": ["kp-positive-negative-numbers"],
                "text": "正数和负数可用于表示相反意义的量。",
                "review_status": "draft",
            },
            {
                "id": "rag-ch1-kp-number-line-summary",
                "source_ref": "llm-draft-teaching-design",
                "content_type": "concept_summary",
                "chapter_id": "ch1",
                "knowledge_point_ids": ["kp-number-line"],
                "text": "数轴用原点、正方向和单位长度表示数。",
                "review_status": "draft",
            },
        ]
    )
    service = MongoTextbookRagService(collection=collection)

    context = service.retrieve("支出 6 元怎么用正数和负数表示？")

    assert "MongoDB 教材 RAG 检索结果" in context
    assert "rag-ch1-kp-positive-negative-summary" in context
    assert "kp-positive-negative-numbers" in context
    assert collection.last_filter is not None
    assert collection.filters


def test_mongo_textbook_rag_escapes_regex_tokens() -> None:
    collection = FakeTextbookChunksCollection([])
    service = MongoTextbookRagService(collection=collection)

    service.retrieve("2(x - 3) = 10")

    lexical_filter = next(filter_doc for filter_doc in collection.filters if "$or" in filter_doc)
    regex_values = [clause["text"]["$regex"] for clause in lexical_filter["$or"] if "text" in clause]
    assert "2\\(x" in regex_values
    assert "\\-" in regex_values


def test_mongo_textbook_rag_uses_multi_route_rerank_for_error_context() -> None:
    collection = FakeTextbookChunksCollection(
        [
            {
                "id": "rag-ch1-kp-number-line-summary",
                "source_ref": "llm-draft-teaching-design",
                "content_type": "concept_summary",
                "chapter_id": "ch1",
                "knowledge_point_ids": ["kp-number-line"],
                "source_section_id": "ch1-sec3",
                "teaching_phase": "explanation",
                "retrieval_tags": ["数轴", "原点"],
                "difficulty": "foundational",
                "text": "数轴用原点、正方向和单位长度表示数。",
                "review_status": "draft",
            },
            {
                "id": "rag-ch1-kp-positive-negative-numbers-error-contrast-1",
                "source_ref": "llm-draft-teaching-design",
                "content_type": "error_contrast",
                "chapter_id": "ch1",
                "knowledge_point_ids": ["kp-positive-negative-numbers"],
                "source_section_id": "ch1-sec1",
                "teaching_phase": "correction",
                "retrieval_tags": ["相反意义", "收入", "支出", "kp-positive-negative-numbers"],
                "difficulty": "introductory",
                "student_error_pattern_ids": [
                    "error-pattern:ch1-kp-positive-negative-numbers-error-contrast-1"
                ],
                "text": "错误示例：支出 6 元写作 +6；错误原因：符号表示方向。",
                "review_status": "draft",
            },
            {
                "id": "rag-ch1-kp-positive-negative-numbers-opening",
                "source_ref": "llm-draft-teaching-design",
                "content_type": "lesson_opening",
                "chapter_id": "ch1",
                "knowledge_point_ids": ["kp-positive-negative-numbers"],
                "source_section_id": "ch1-sec1",
                "teaching_phase": "opening",
                "retrieval_tags": ["收入", "支出", "kp-positive-negative-numbers"],
                "difficulty": "introductory",
                "text": "适合的课堂导入：从温度、海拔、收入支出等相反意义的量导入。",
                "review_status": "draft",
            },
        ]
    )
    service = MongoTextbookRagService(collection=collection, max_chunks=2)

    context = service.retrieve_for_turn(
        RagTurnContext(
            query="*6",
            current_chapter_id="ch1",
            current_section_id="ch1-sec1",
            current_knowledge_point_id="kp-positive-negative-numbers",
            teaching_mode="adaptive_remediation",
            learner_state="step_error",
            current_question="如果收入10元记作+10，那支出6元应该怎么记？",
            student_answer_status="incorrect_symbol",
        )
    )

    assert "多路召回 + rerank" in context
    assert context.index("error-contrast") < context.index("opening")
    assert "routes=" in context
    assert any(filter_doc.get("knowledge_point_ids") == "kp-positive-negative-numbers" for filter_doc in collection.filters)
    assert any(filter_doc.get("content_type", {}).get("$in") for filter_doc in collection.filters)


def test_get_rag_service_can_select_mongodb_backend(monkeypatch) -> None:
    monkeypatch.setattr(rag.settings, "rag_backend", "mongodb")

    service = get_rag_service()

    assert isinstance(service, MongoTextbookRagService)


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


def test_agent_harness_retrieves_rag_after_lesson_state_and_planner() -> None:
    captured = {}

    class CapturingProvider:
        def generate_reply(self, prompt):
            captured["retrieved_context"] = prompt.retrieved_context
            return "先看刚才那题，* 不是正负号。"

    class CapturingRagService(RagService):
        def retrieve_for_turn(self, context):
            captured["rag_context"] = context
            return "captured textbook chunks"

    from app.schemas.lesson import LessonSessionCreate
    from app.schemas.teacher import StudentContext, TeacherChatRequest
    from app.services.agent_harness import AgentHarness
    from app.services.deepagents_runtime import DeepAgentsTeachingRuntime
    from app.services.lesson_store import InMemoryLessonRepository
    from app.services.memory import MemoryService
    from app.services.planner import PlannerService
    from app.services.skill_registry import SkillRegistry

    repository = InMemoryLessonRepository()
    session = repository.create_session(
        LessonSessionCreate(
            student_id="rag-order-student",
            grade="初一",
            subject="数学",
            title="正数和负数",
            lesson_goal="理解正负数表示相反意义的量",
        )
    )
    repository.update_session_state(
        session.id,
        current_skill_id="opent-teacher-rj-junior-math-grade7-vol1-kp-positive-negative-numbers",
        current_knowledge_point_id="kp-positive-negative-numbers",
        current_section_id="ch1-sec1",
        current_chapter_id="ch1",
    )
    for index in range(7):
        repository.append_message(
            session_id=session.id,
            role="student" if index % 2 else "teacher",
            content=f"完整课堂历史{index}",
        )
    repository.append_message(
        session_id=session.id,
        role="teacher",
        content="如果收入10元记作+10，那支出6元应该怎么记？",
    )
    service = AgentHarness(
        memory_service=MemoryService(),
        rag_service=CapturingRagService(),
        skill_registry=SkillRegistry(),
        llm_provider=CapturingProvider(),
        lesson_repository=repository,
        deepagents_runtime=DeepAgentsTeachingRuntime(
            memory_service=MemoryService(),
            lesson_repository=repository,
            rag_service=CapturingRagService(),
        ),
        planner_service=PlannerService(),
    )

    service.reply(
        TeacherChatRequest(
            message="*6",
            context=StudentContext(
                student_id="rag-order-student",
                grade="初一",
                subject="数学",
                session_id=session.id,
            ),
        )
    )

    rag_context = captured["rag_context"]
    assert rag_context.current_knowledge_point_id == "kp-positive-negative-numbers"
    assert rag_context.current_section_id == "ch1-sec1"
    assert rag_context.student_answer_status == "incorrect_symbol"
    assert any("完整课堂历史0" in line for line in rag_context.recent_messages)
    assert rag_context.teaching_mode in {"adaptive_remediation", "active_lesson"}
    assert captured["retrieved_context"] == "captured textbook chunks"
