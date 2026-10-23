from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-secret-change-me-in-production-0000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    app_name: str = "Chalkback"
    environment: str = "development"
    database_url: str = "sqlite:///./data/chalkback.db"
    data_dir: Path = Path("./data")
    public_base_url: str = "http://localhost:8000"
    app_base_url: str = "http://localhost:5173"
    cors_origins: list[str] = ["http://localhost:5173"]

    jwt_secret: str = DEV_JWT_SECRET
    jwt_ttl_hours: int = 24 * 7
    allow_registration: bool = True

    # AI. Without a key the pipeline runs in deterministic mock mode.
    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-5-5"
    reconstruct_effort: str = "high"
    summary_effort: str = "medium"

    # Reminders
    telegram_bot_token: str | None = None
    # Listen for /start <code> and /stop messages (long polling; no webhook to configure).
    telegram_polling: bool = True
    telegram_link_days: int = 14
    resend_api_key: str | None = None
    email_from: str = "Chalkback <recaps@chalkback.local>"
    reminder_lead_hours: int = 24
    reminder_interval_minutes: int = 15
    scheduler_enabled: bool = True

    # Demo data
    seed_demo: bool = True
    demo_teacher_email: str = "teacher@demo.chalkback"
    demo_password: str = "demo-password"

    @model_validator(mode="after")
    def _require_real_secret_in_production(self) -> "Settings":
        if self.environment == "production" and self.jwt_secret == DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET must be set in production")
        return self

    @property
    def ai_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def sources_dir(self) -> Path:
        """Original uploaded documents; never served over HTTP."""
        return self.data_dir / "sources"


@lru_cache
def get_settings() -> Settings:
    return Settings()
