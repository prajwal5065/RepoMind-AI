"""
Application settings loaded from environment variables / .env file.

Security-sensitive fields
--------------------------
API_KEY          Required. Set to a long random string (e.g. openssl rand -hex 32).
                 All protected API endpoints require X-API-Key: <value> header.
ALLOWED_ORIGINS  Comma-separated list of allowed CORS origins.
                 Example: "https://myapp.com,https://staging.myapp.com"
DEBUG            Set to false in production. When false, stack traces are
                 never included in API error responses.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM providers
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    DEFAULT_LLM_PROVIDER: str = "groq"

    # Storage
    FAISS_INDEX_PATH: str = "data/faiss_index"
    UPLOAD_DIR: str = "data/uploads"

    # Security — intentionally no default so the app refuses to start
    # without an explicit key set in the environment / .env file.
    API_KEY: str = ""

    # CORS — restrict to known origins in production
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Set DEBUG=true only in local development.
    # When False, internal error details are never returned to clients.
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
