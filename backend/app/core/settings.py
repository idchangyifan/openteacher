from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "OpenTeacher"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://openteacher:openteacher@localhost:5432/openteacher"
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8")


settings = Settings()
