from fastapi import APIRouter, Depends

from app.schemas.teacher import TeacherChatRequest, TeacherChatResponse
from app.services.agent_harness import AgentHarness, get_agent_harness

router = APIRouter()


@router.post("/chat", response_model=TeacherChatResponse)
def chat_with_teacher(
    request: TeacherChatRequest,
    harness: AgentHarness = Depends(get_agent_harness),
) -> TeacherChatResponse:
    return harness.reply(request)
