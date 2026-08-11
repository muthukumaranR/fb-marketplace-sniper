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

    # Below this relevance score (0-1), skip the email even if the price looks great
    notify_min_relevance: float = 0.5

    # Facebook
    fb_state_path: str = "~/.config/marketswipe/fb_state.json"

    # LLM (provider-agnostic via LiteLLM)
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    llm_model: str = ""

    # Blablador (Helmholtz/FZ Jülich, OpenAI-compatible) — preferred provider
    blablador_api_key: str = ""
    blablador_url: str = "https://api.blablador.fz-juelich.de/v1"
    blablador_model_alias: str = "alias-fast"
    blablador_model_large: str = "alias-kimi-k3-1m"

    # Scan
    scan_interval_minutes: int = 30

    # Database
    db_path: str = "marketswipe.db"

    @property
    def fb_state_resolved(self) -> Path:
        return Path(self.fb_state_path).expanduser()

    @property
    def blablador_base_url(self) -> str:
        """Blablador URL without the trailing slash LiteLLM would double up."""
        return self.blablador_url.rstrip("/")

    @property
    def resolved_llm_model(self) -> str:
        """Pick the LLM model based on which API key is configured."""
        if self.llm_model:
            return self.llm_model
        if self.blablador_api_key:
            return f"openai/{self.blablador_model_alias}"
        if self.gemini_api_key:
            return "gemini/gemini-2.0-flash"
        if self.anthropic_api_key:
            return "claude-haiku-4-5-20251001"
        raise RuntimeError(
            "No LLM API key configured. Set BLABLADOR_API_KEY, GEMINI_API_KEY, "
            "or ANTHROPIC_API_KEY in .env"
        )

    def llm_call_kwargs(self, large: bool = False) -> dict:
        """
        Model + routing kwargs to splat into a LiteLLM completion call.

        `large=True` selects BLABLADOR_MODEL_LARGE — the long-context reasoning
        alias. It is far slower than the default (measured ~2.5 min vs ~2s for a
        price lookup) and needs stream=True, since Blablador drops non-streamed
        requests at ~50s. Use it only for genuinely long-context work.
        """
        if large:
            if not self.blablador_api_key:
                raise RuntimeError("large=True requires BLABLADOR_API_KEY in .env")
            return {
                "model": f"openai/{self.blablador_model_large}",
                "api_base": self.blablador_base_url,
                "api_key": self.blablador_api_key,
            }

        model = self.resolved_llm_model
        kwargs = {"model": model}
        if self.blablador_api_key and model == f"openai/{self.blablador_model_alias}":
            kwargs["api_base"] = self.blablador_base_url
            kwargs["api_key"] = self.blablador_api_key
        return kwargs


settings = Settings()
