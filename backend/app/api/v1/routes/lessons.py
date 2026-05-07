from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.schemas.lesson import (
    LessonSession,
    LessonSessionCreate,
    LessonSessionDetail,
    LessonSessionSummary,
)
from app.services.lesson_store import LessonRepository, get_lesson_repository
from app.services.memory import MemoryService, get_memory_service

router = APIRouter()


@router.post("", response_model=LessonSession)
def create_lesson_session(
    request: LessonSessionCreate,
    lesson_repository: LessonRepository = Depends(get_lesson_repository),
) -> LessonSession:
    return lesson_repository.create_session(request)


@router.get("", response_model=list[LessonSessionSummary])
def list_lesson_sessions(
    student_id: str = Query(default="demo-student"),
    lesson_repository: LessonRepository = Depends(get_lesson_repository),
) -> list[LessonSessionSummary]:
    return lesson_repository.list_sessions(student_id)


@router.get("/{session_id}", response_model=LessonSessionDetail)
def get_lesson_session(
    session_id: str,
    lesson_repository: LessonRepository = Depends(get_lesson_repository),
) -> LessonSessionDetail:
    detail = lesson_repository.get_session_detail(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Lesson session not found")
    return detail


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lesson_session(
    session_id: str,
    lesson_repository: LessonRepository = Depends(get_lesson_repository),
    memory_service: MemoryService = Depends(get_memory_service),
) -> Response:
    deleted = lesson_repository.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Lesson session not found")

    memory_service.mark_source_session_deleted(session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
