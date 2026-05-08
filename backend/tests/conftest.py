import pytest

from app.services import lesson_store, llm_provider, memory, memory_update_queue
from app.services import rag
from app.core import settings


@pytest.fixture(autouse=True)
def use_mock_llm_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "mock")
    monkeypatch.setattr(settings.settings, "agent_runtime", "provider")
    monkeypatch.setattr(llm_provider.settings, "agent_runtime", "provider")
    monkeypatch.setattr(rag.settings, "rag_backend", "mock")
    monkeypatch.setattr(memory.settings, "memory_backend", "mock")
    monkeypatch.setattr(settings.settings, "memory_update_queue_backend", "inline")
    monkeypatch.setattr(memory_update_queue.settings, "memory_update_queue_backend", "inline")
    monkeypatch.setattr(lesson_store.settings, "agent_runtime", "provider")
    monkeypatch.setattr(lesson_store.settings, "lesson_store_backend", "memory")
    lesson_store.get_mongo_lesson_repository.cache_clear()
    memory.get_mongo_memory_service.cache_clear()
    lesson_store._memory_repository.sessions.clear()
    lesson_store._memory_repository.messages.clear()
