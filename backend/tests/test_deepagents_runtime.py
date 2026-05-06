from typing import Any

from app.schemas.lesson import LessonSessionCreate
from app.schemas.teacher import StudentContext, TeacherChatRequest
from app.services.deepagents_runtime import DeepAgentsTeachingRuntime
from app.services.lesson_store import InMemoryLessonRepository
from app.services.llm_provider import TeacherPrompt
from app.services.memory import MemoryService
from app.services.rag import RagService


def make_prompt() -> TeacherPrompt:
    return TeacherPrompt(
        message="我想开始学浮力",
        grade="初一",
        subject="物理",
        teacher_style="严格但温暖",
        skill_name="Universal Teacher Core + 通用知识 Skill",
        skill_guidance="教师核心规则 + 通用知识规则",
        memory_summary="学生需要更多诊断问题",
        retrieved_context="浮力概念",
        core_skill_name="Universal Teacher Core",
        core_skill_guidance="主动授课；识别掌握信号。",
        knowledge_skill_name="通用知识 Skill",
        knowledge_skill_guidance="根据学科选择教学动作。",
        planner_context=(
            "teaching_mode=active_lesson\n"
            "learner_state=insufficient_information\n"
            "next_teacher_goal=继续当前诊断题，先评价学生回答。"
        ),
    )


def test_deepagents_system_prompt_prioritizes_active_teaching() -> None:
    runtime = DeepAgentsTeachingRuntime(
        memory_service=MemoryService(),
        lesson_repository=InMemoryLessonRepository(),
    )

    system_prompt = runtime._build_system_prompt(make_prompt())

    assert "主动授课是主轴" in system_prompt
    assert "Executor" in system_prompt
    assert "teaching_mode=active_lesson" in system_prompt
    assert "不要把所有输入都当成一元一次方程解题" in system_prompt
    assert "先确认正确" in system_prompt


def test_deepagents_tools_can_read_memory_and_lesson_state() -> None:
    repository = InMemoryLessonRepository()
    session = repository.create_session(
        request=LessonSessionCreate(
            student_id="deepagents-test-student",
            subject="物理",
            title="浮力入门",
            lesson_goal="理解浮力和重力的关系",
        )
    )
    request = TeacherChatRequest(
        message="老师，我们继续上次的课",
        context=StudentContext(
            student_id="deepagents-test-student",
            subject="物理",
            session_id=session.id,
        ),
    )
    runtime = DeepAgentsTeachingRuntime(memory_service=MemoryService(), lesson_repository=repository)

    tools = {tool.__name__: tool for tool in runtime._build_tools(request)}

    assert "移项符号容易错" in tools["retrieve_student_memory"]("浮力")
    lesson_state = tools["load_lesson_state"]()
    assert "浮力入门" in lesson_state
    assert "理解浮力和重力的关系" in lesson_state


def test_deepagents_tools_can_retrieve_textbook_chunks_with_graph_state() -> None:
    captured = {}

    class CapturingRagService(RagService):
        def retrieve_for_turn(self, context):
            captured["context"] = context
            return "reranked textbook chunks"

    repository = InMemoryLessonRepository()
    session = repository.create_session(
        request=LessonSessionCreate(
            student_id="deepagents-rag-student",
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
    repository.append_message(
        session_id=session.id,
        role="teacher",
        content="如果收入10元记作+10，那支出6元应该怎么记？",
    )
    request = TeacherChatRequest(
        message="*6",
        context=StudentContext(
            student_id="deepagents-rag-student",
            grade="初一",
            subject="数学",
            session_id=session.id,
        ),
    )
    runtime = DeepAgentsTeachingRuntime(
        memory_service=MemoryService(),
        lesson_repository=repository,
        rag_service=CapturingRagService(),
    )
    graph_state = runtime._build_graph_state(request, make_prompt())
    tools = {tool.__name__: tool for tool in runtime._build_tools(request, make_prompt(), graph_state)}

    result = tools["retrieve_textbook_chunks"]("*6")

    assert result == "reranked textbook chunks"
    assert captured["context"].current_knowledge_point_id == "kp-positive-negative-numbers"
    assert captured["context"].student_answer_status == "incorrect_symbol"
    assert captured["context"].current_question == "如果收入10元记作+10，那支出6元应该怎么记？"


def test_teaching_graph_state_uses_session_id_as_thread_and_keeps_lesson_state() -> None:
    repository = InMemoryLessonRepository()
    session = repository.create_session(
        request=LessonSessionCreate(
            student_id="graph-state-student",
            subject="数学",
            title="正数和负数",
            lesson_goal="理解正负数表示相反意义的量",
        )
    )
    repository.update_session_state(
        session.id,
        current_skill_id="opent-teacher-rj-junior-math-grade7-vol1-kp-positive-negative-numbers",
        current_knowledge_point_id="kp-positive-negative-numbers",
        current_chapter_id="ch1",
    )
    repository.append_message(
        session_id=session.id,
        role="teacher",
        content="如果收入10元记作+10，那支出6元应该怎么记？",
    )
    repository.append_message(session_id=session.id, role="student", content="*6")
    request = TeacherChatRequest(
        message="*6",
        context=StudentContext(
            student_id="graph-state-student",
            grade="初一",
            subject="数学",
            session_id=session.id,
        ),
    )
    runtime = DeepAgentsTeachingRuntime(memory_service=MemoryService(), lesson_repository=repository)

    graph_state = runtime._build_graph_state(request, make_prompt())
    payload = graph_state.to_payload()

    assert graph_state.thread_id == session.id
    assert graph_state.lesson_state.current_chapter_id == "ch1"
    assert graph_state.lesson_state.current_knowledge_point_id == "kp-positive-negative-numbers"
    assert graph_state.lesson_state.current_skill_id.endswith("positive-negative-numbers")
    assert graph_state.current_question == "如果收入10元记作+10，那支出6元应该怎么记？"
    assert graph_state.student_answer_status == "incorrect_symbol"
    assert "* 不是正负号" in graph_state.student_answer_feedback
    assert "不要直接说出完整答案" in graph_state.next_teaching_action
    assert payload["lesson_state"]["current_skill_id"].endswith("positive-negative-numbers")
    assert payload["messages"][-1] == {"role": "student", "content": "*6"}


def test_deepagents_short_term_memory_middleware_includes_full_session_context() -> None:
    repository = InMemoryLessonRepository()
    session = repository.create_session(
        request=LessonSessionCreate(
            student_id="short-term-mw-student",
            subject="数学",
            title="正数和负数",
            lesson_goal="理解正负数表示相反意义的量",
        )
    )
    for role, content in [
        ("teacher", "如果收入 10 元记作 +10，那么支出 6 元应该怎么记？"),
        ("student", "&6"),
        ("teacher", "你写的 & 不是正负号。支出和收入方向相反，应该用 + 还是 -？"),
        ("student", "与 6啊"),
    ]:
        repository.append_message(session_id=session.id, role=role, content=content)
    request = TeacherChatRequest(
        message="与 6啊",
        context=StudentContext(
            student_id="short-term-mw-student",
            grade="初一",
            subject="数学",
            session_id=session.id,
        ),
    )
    runtime = DeepAgentsTeachingRuntime(memory_service=MemoryService(), lesson_repository=repository)

    graph_state = runtime._build_graph_state(request, make_prompt())
    context = runtime._format_short_term_context(graph_state)

    assert "DeepAgents middleware" in context
    assert "完整课堂记录" in context
    assert "&6" in context
    assert "与 6啊" in context
    assert "禁止重新宣布学习目标或重启 lesson_start" in context
    assert graph_state.student_answer_status == "invalid_symbol"


def test_deepagents_invocation_passes_mongodb_checkpointer_and_thread_config() -> None:
    captured: dict[str, Any] = {}

    class FakeAgent:
        def invoke(self, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
            captured["payload"] = payload
            captured["config"] = config
            return {"messages": [{"role": "assistant", "content": "继续看刚才那题：*6 不对。"}]}

    def fake_create_deep_agent(**kwargs: Any) -> FakeAgent:
        captured["create_kwargs"] = kwargs
        return FakeAgent()

    repository = InMemoryLessonRepository()
    session = repository.create_session(
        request=LessonSessionCreate(
            student_id="deepagents-thread-student",
            subject="数学",
            title="正数和负数",
            lesson_goal="理解正负数表示相反意义的量",
        )
    )
    request = TeacherChatRequest(
        message="-6",
        context=StudentContext(
            student_id="deepagents-thread-student",
            grade="初一",
            subject="数学",
            session_id=session.id,
        ),
    )
    runtime = DeepAgentsTeachingRuntime(memory_service=MemoryService(), lesson_repository=repository)
    runtime._load_create_deep_agent = lambda: fake_create_deep_agent  # type: ignore[method-assign]
    runtime._build_model = lambda: "fake-model"  # type: ignore[method-assign]
    runtime._build_checkpointer = lambda: "fake-mongodb-checkpointer"  # type: ignore[method-assign]

    result = runtime.generate_reply(request, make_prompt())

    assert result.reply == "继续看刚才那题：*6 不对。"
    assert captured["create_kwargs"]["checkpointer"] == "fake-mongodb-checkpointer"
    assert captured["config"]["configurable"]["thread_id"] == session.id
    assert captured["config"]["metadata"]["session_id"] == session.id
    user_message = captured["payload"]["messages"][0]["content"]
    assert f"thread_id：{session.id}" in user_message


def test_teaching_graph_state_marks_negative_six_correct_for_current_diagnostic() -> None:
    repository = InMemoryLessonRepository()
    session = repository.create_session(
        request=LessonSessionCreate(
            student_id="graph-state-correct-student",
            subject="数学",
            title="正数和负数",
        )
    )
    repository.append_message(
        session_id=session.id,
        role="teacher",
        content="如果收入10元记作+10，那支出6元应该怎么记？",
    )
    repository.append_message(session_id=session.id, role="student", content="-6")
    request = TeacherChatRequest(
        message="-6",
        context=StudentContext(
            student_id="graph-state-correct-student",
            grade="初一",
            subject="数学",
            session_id=session.id,
        ),
    )
    runtime = DeepAgentsTeachingRuntime(memory_service=MemoryService(), lesson_repository=repository)

    graph_state = runtime._build_graph_state(request, make_prompt())

    assert graph_state.student_answer_status == "correct"
    assert "先确认正确" in graph_state.student_answer_feedback
    assert "不要切到下一题" in graph_state.next_teaching_action
