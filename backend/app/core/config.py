from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_env: str = "development"
    app_host: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/habit_tracker"

    session_secret: str = "change-me"
    app_timezone: str = "Europe/Warsaw"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/api/auth/github/callback"


settings = Settings()
