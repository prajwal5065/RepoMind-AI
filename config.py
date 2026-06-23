from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    GEMINI_API_KEY: str = "your_gemini_api_key_here"
    FAISS_INDEX_PATH: str = "data/faiss_index"
    UPLOAD_DIR: str = "data/uploads"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
