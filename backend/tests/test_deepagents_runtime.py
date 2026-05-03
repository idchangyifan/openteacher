from app.schemas.lesson import LessonSessionCreate
from app.schemas.teacher import StudentContext, TeacherChatRequest
from app.services.deepagents_runtime import DeepAgentsTeachingRuntime
from app.services.lesson_store import InMemoryLessonRepository
from app.services.llm_provider import TeacherPrompt
from app.services.memory import MemoryService


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
    )


def test_deepagents_system_prompt_prioritizes_active_teaching() -> None:
    runtime = DeepAgentsTeachingRuntime(
        memory_service=MemoryService(),
        lesson_repository=InMemoryLessonRepository(),
    )

    system_prompt = runtime._build_system_prompt(make_prompt())

    assert "主动授课是主轴" in system_prompt
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
