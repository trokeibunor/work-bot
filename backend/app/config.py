import os
import json
from typing import List, Union, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://jate_admin:jate_secure_password_2026@db:5432/jate_db"

    # Redis & Celery
    REDIS_URL: str = "redis://:jate_redis_password_2026@redis:6379/0"
    CELERY_BROKER_URL: str = "redis://:jate_redis_password_2026@redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://:jate_redis_password_2026@redis:6379/1"

    # LLM Provider: OpenAI or Google Gemini
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: Optional[str] = None
    GEMINI_API_KEY: str = ""

    # Storage
    STORAGE_DIR: str = "/app/storage/pdfs"

    # CORS
    CORS_ORIGINS: Union[List[str], str] = ["*"]

    # Reddit Integration
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USER_AGENT: str = "JATE-Bot/1.0.0"

    # Operational targets
    DAILY_APPLICATION_TARGET: int = 50

    @property
    def effective_llm_key(self) -> str:
        if self.GEMINI_API_KEY.strip():
            return self.GEMINI_API_KEY.strip()
        return self.OPENAI_API_KEY.strip()

    @property
    def is_gemini(self) -> bool:
        key = self.effective_llm_key
        return bool(self.GEMINI_API_KEY.strip()) or key.startswith("AIza")

    @property
    def effective_base_url(self) -> Optional[str]:
        if self.OPENAI_BASE_URL and self.OPENAI_BASE_URL.strip():
            return self.OPENAI_BASE_URL.strip()
        if self.is_gemini:
            return "https://generativelanguage.googleapis.com/v1beta/openai/"
        return None

    @property
    def effective_model(self) -> str:
        if self.is_gemini:
            # If user explicitly specified a gemini model that isn't deprecated, use it; otherwise default to gemini-flash-latest
            if "gemini" in self.OPENAI_MODEL.lower() and "1.5" not in self.OPENAI_MODEL and "2.5" not in self.OPENAI_MODEL:
                return self.OPENAI_MODEL
            return "gemini-flash-latest"
        return self.OPENAI_MODEL

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
