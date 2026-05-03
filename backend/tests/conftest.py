import pytest

from app.services import lesson_store, llm_provider


@pytest.fixture(autouse=True)
def use_mock_llm_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "mock")
    monkeypatch.setattr(lesson_store.settings, "lesson_store_backend", "memory")
    lesson_store.get_mongo_lesson_repository.cache_clear()
    lesson_store._memory_repository.sessions.clear()
    lesson_store._memory_repository.messages.clear()
