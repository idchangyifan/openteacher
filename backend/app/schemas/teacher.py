from pydantic import BaseModel, Field


class StudentContext(BaseModel):
    student_id: str = "demo-student"
    grade: str = "初一"
    subject: str = "数学"
    teacher_style: str = "严格但温暖"


class TeacherChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    context: StudentContext = Field(default_factory=StudentContext)


class MemoryEvent(BaseModel):
    kind: str
    summary: str


class TeacherChatResponse(BaseModel):
    reply: str
    skill_id: str
    memory_events: list[MemoryEvent] = Field(default_factory=list)
