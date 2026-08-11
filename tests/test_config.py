import pytest

from backend.config import Settings

LLM_ENV_VARS = [
    "BLABLADOR_API_KEY",
    "BLABLADOR_URL",
    "BLABLADOR_MODEL_ALIAS",
    "BLABLADOR_MODEL_LARGE",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "LLM_MODEL",
]


@pytest.fixture(autouse=True)
def clean_llm_env(monkeypatch):
    """
    Importing litellm runs load_dotenv(), which pushes the developer's real .env
    into os.environ — so _env_file=None alone does not isolate these tests.
    """
    for var in LLM_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def make_settings(**overrides) -> Settings:
    """Settings built in isolation from the developer's real .env file."""
    return Settings(_env_file=None, **overrides)


class TestResolvedLlmModel:
    def test_blablador_preferred_over_other_providers(self):
        s = make_settings(
            blablador_api_key="bk",
            blablador_model_alias="alias-kimi-k3-1m",
            gemini_api_key="gk",
            anthropic_api_key="ak",
        )
        assert s.resolved_llm_model == "openai/alias-kimi-k3-1m"

    def test_blablador_uses_default_alias(self):
        s = make_settings(blablador_api_key="bk")
        assert s.resolved_llm_model == "openai/alias-fast"

    def test_explicit_llm_model_wins(self):
        s = make_settings(llm_model="gemini/gemini-2.0-flash", blablador_api_key="bk")
        assert s.resolved_llm_model == "gemini/gemini-2.0-flash"

    def test_falls_back_to_gemini(self):
        s = make_settings(gemini_api_key="gk", anthropic_api_key="ak")
        assert s.resolved_llm_model == "gemini/gemini-2.0-flash"

    def test_falls_back_to_anthropic(self):
        s = make_settings(anthropic_api_key="ak")
        assert s.resolved_llm_model == "claude-haiku-4-5-20251001"

    def test_no_key_raises(self):
        s = make_settings()
        with pytest.raises(RuntimeError, match="BLABLADOR_API_KEY"):
            s.resolved_llm_model


class TestBlabladorBaseUrl:
    def test_trailing_slash_stripped(self):
        s = make_settings(blablador_url="https://api.blablador.fz-juelich.de/v1/")
        assert s.blablador_base_url == "https://api.blablador.fz-juelich.de/v1"

    def test_url_without_slash_unchanged(self):
        s = make_settings(blablador_url="https://api.blablador.fz-juelich.de/v1")
        assert s.blablador_base_url == "https://api.blablador.fz-juelich.de/v1"


class TestLlmCallKwargs:
    def test_blablador_routes_to_custom_endpoint(self):
        s = make_settings(
            blablador_api_key="bk",
            blablador_model_alias="alias-kimi-k3-1m",
            blablador_url="https://api.blablador.fz-juelich.de/v1/",
        )
        assert s.llm_call_kwargs() == {
            "model": "openai/alias-kimi-k3-1m",
            "api_base": "https://api.blablador.fz-juelich.de/v1",
            "api_key": "bk",
        }

    def test_explicit_blablador_model_still_routed(self):
        s = make_settings(
            blablador_api_key="bk",
            blablador_model_alias="alias-fast",
            llm_model="openai/alias-fast",
        )
        assert s.llm_call_kwargs()["api_base"] == "https://api.blablador.fz-juelich.de/v1"

    def test_non_blablador_openai_model_not_hijacked(self):
        """An explicit OpenAI model must not be pointed at Blablador's endpoint."""
        s = make_settings(blablador_api_key="bk", llm_model="openai/gpt-4o")
        assert s.llm_call_kwargs() == {"model": "openai/gpt-4o"}

    def test_gemini_gets_no_routing_kwargs(self):
        s = make_settings(gemini_api_key="gk")
        assert s.llm_call_kwargs() == {"model": "gemini/gemini-2.0-flash"}


class TestLargeModelSlot:
    def test_large_selects_the_long_context_alias(self):
        s = make_settings(
            blablador_api_key="bk",
            blablador_model_alias="alias-fast",
            blablador_model_large="alias-kimi-k3-1m",
        )
        assert s.llm_call_kwargs(large=True) == {
            "model": "openai/alias-kimi-k3-1m",
            "api_base": "https://api.blablador.fz-juelich.de/v1",
            "api_key": "bk",
        }

    def test_default_call_still_uses_the_fast_alias(self):
        s = make_settings(blablador_api_key="bk", blablador_model_large="alias-kimi-k3-1m")
        assert s.llm_call_kwargs()["model"] == "openai/alias-fast"

    def test_large_ignores_llm_model_override(self):
        """LLM_MODEL points at the default provider; it must not shadow the large slot."""
        s = make_settings(blablador_api_key="bk", llm_model="gemini/gemini-2.0-flash")
        assert s.llm_call_kwargs(large=True)["model"] == "openai/alias-kimi-k3-1m"

    def test_large_without_blablador_key_raises(self):
        s = make_settings(gemini_api_key="gk")
        with pytest.raises(RuntimeError, match="BLABLADOR_API_KEY"):
            s.llm_call_kwargs(large=True)
