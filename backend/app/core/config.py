from pathlib import Path
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    PROJECT_NAME: str = "WasteFlow AI Intelligence Service"
    API_V1_STR: str = "/api/v1"

    # --- Gemini (Spec 5.3, 8.2: provider/model are backend configuration) ---
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.8-flash"
    GEMINI_TEMPERATURE: float = 0.2
    GEMINI_TIMEOUT_SECONDS: float = 60.0
    GEMINI_MAX_RETRIES: int = 2          # retries only for transient errors (Spec 8)
    AI_VALIDATION_RETRIES: int = 1       # one corrective re-ask when output fails layers 3-6
    PROMPT_VERSION: str = "wasteflow-ai-v1"
    AI_OUTPUT_LANGUAGE: str = "Bahasa Indonesia"

    # Mock provider is for local development/tests ONLY. Never enable in production.
    AI_ALLOW_MOCK: bool = False

    # --- Guardrails (Spec 7.1 duplicate request, 8.1 payload/frequency limits) ---
    AI_ANALYSIS_COOLDOWN_SECONDS: int = 30
    AI_MAX_PAYLOAD_BYTES: int = 60_000
    AI_NUMERIC_REL_TOLERANCE: float = 0.01

    # --- Database ---
    DATABASE_URL: str = f"sqlite:///{(BACKEND_DIR / 'wasteflow.db').as_posix()}"

    # --- Security (Spec 8.1: restrict CORS) ---
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Dev-only seeding endpoint (POST /optimization/runs). Disable when embedded
    # in the main WasteFlow system, where runs are created by the solver.
    ENABLE_DEV_ENDPOINTS: bool = True

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str) and not v.strip().startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def _resolve_sqlite_path(cls, v: str) -> str:
        # Make relative sqlite paths independent of the current working directory.
        prefix = "sqlite:///./"
        if v.startswith(prefix):
            return f"sqlite:///{(BACKEND_DIR / v[len(prefix):]).as_posix()}"
        return v

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
