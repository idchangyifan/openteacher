from fastapi import APIRouter

from app.api.v1.routes import health, lessons, teacher

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(lessons.router, prefix="/lessons", tags=["lessons"])
api_router.include_router(teacher.router, prefix="/teacher", tags=["teacher"])
