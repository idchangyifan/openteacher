import pytest

from app.services import llm_provider


@pytest.fixture(autouse=True)
def use_mock_llm_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_provider.settings, "llm_provider", "mock")
