from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "OpenTeacher"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://openteacher:openteacher@localhost:5432/openteacher"
    frontend_origin: str = "http://localhost:5173"
    memory_backend: str = "mock"
    rag_backend: str = "mock"
    skills_dir: Path = ROOT_DIR / "skills"
    llm_provider: str = "mock"
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = ""
    openai_max_output_tokens: int = 700
    openai_timeout_seconds: float = 30.0
    doubao_api_key: SecretStr | None = None
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    doubao_model: str = ""
    doubao_max_tokens: int = 700
    doubao_timeout_seconds: float = 30.0

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origin.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
    )


settings = Settings()
