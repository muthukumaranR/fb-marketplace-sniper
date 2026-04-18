from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_pass: str = ""
    notify_email: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Location defaults
    default_location: str = "Huntsville, AL"
    default_radius: int = 20

    # Deal thresholds
    great_deal_threshold: float = 0.60
    good_deal_threshold: float = 0.75

    # Relevance gating: skip notifications when relevance falls below this.
    # Scored listings with score < threshold are still persisted — just not emailed.
    notify_min_relevance: float = 0.5

    # Facebook
    fb_state_path: str = "~/.config/sniper/fb_state.json"

    # LLM (provider-agnostic via LiteLLM)
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    llm_model: str = ""

    # Scan
    scan_interval_minutes: int = 30

    # Database
    db_path: str = "sniper.db"

    @property
    def fb_state_resolved(self) -> Path:
        return Path(self.fb_state_path).expanduser()

    @property
    def resolved_llm_model(self) -> str:
        """Pick the LLM model based on which API key is configured."""
        if self.llm_model:
            return self.llm_model
        if self.gemini_api_key:
            return "gemini/gemini-2.0-flash"
        if self.anthropic_api_key:
            return "claude-haiku-4-5-20251001"
        raise RuntimeError("No LLM API key configured. Set GEMINI_API_KEY or ANTHROPIC_API_KEY in .env")


settings = Settings()
