from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.lesson import (
    LessonSession,
    LessonSessionCreate,
    LessonSessionDetail,
    LessonSessionSummary,
)
from app.services.lesson_store import LessonRepository, get_lesson_repository

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
