from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://inboxguard:inboxguard@localhost:5434/inboxguard"
    token_encryption_key: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    frontend_origin: str = ""

    telegram_bot_token: str = ""
    registry_path: str = "data/replai-registry.xlsx"

    # Founder-only: one Gmail address receives the daily pending-reply digest.
    founder_alert_email: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    digest_hour: int = 9

    llm_provider: Literal["openai_compatible", "anthropic"] = "openai_compatible"
    llm_key: str = ""
    llm_model: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_json_mode: bool = True
    llm_disable_thinking: bool = False
    llm_reasoning_effort: str | None = None
    llm_max_tokens: int = 300
    llm_timeout_s: float = 30
    llm_price_input_per_m: float | None = None
    llm_price_output_per_m: float | None = None

    default_timezone: str = "Asia/Kolkata"

    enable_scheduler: bool = True
    sync_interval_minutes: int = 5  # unused when daily digest job is enabled
    sync_lookback_days: int = 30
    sync_max_threads: int = 100

    # Urgency wait thresholds (hours). Used by later milestones.
    urgency_5_hours: int = 1
    urgency_4_hours: int = 2
    urgency_3_hours: int = 24
    urgency_2_hours: int = 48

    quiet_hours_start: int = 22
    quiet_hours_end: int = 8
    max_realtime_alerts_per_day: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
