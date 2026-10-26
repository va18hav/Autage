import pytest

import services.agent.llm.resolver as resolver_mod
from services.agent.llm import (
    LlmConfigError,
    LlmResolver,
    StepKey,
    get_llm,
    reset_resolver,
    set_resolver,
)
from services.agent.llm.resolver import StepSelection, friendly_error
from services.db.models.credentials import LlmStepConfig
from services.secrets.store import SecretStore


@pytest.mark.anyio
async def test_llm_resolver_load_from_db_and_env_fallback(in_memory_db, monkeypatch):
    monkeypatch.setattr(resolver_mod, "async_session_factory", in_memory_db.factory)

    # Save custom step config for TRIAGE and OpenAI credential in DB
    in_memory_db.add(
        LlmStepConfig(
            step_key=StepKey.TRIAGE,
            provider_id="openai",
            model_id="gpt-4o-mini",
            temperature=0.1,
            max_output_tokens=256,
        )
    )
    await SecretStore.save("openai", {"api_key": "sk-db-key"}, "sk-…key")

    resolver = await LlmResolver.load()
    described = resolver.describe()

    assert described[StepKey.TRIAGE].provider_id == "openai"
    assert described[StepKey.TRIAGE].is_default is False
    assert described[StepKey.RECOMMENDATIONS].is_default is True

    token = set_resolver(resolver)
    try:
        llm = get_llm(StepKey.TRIAGE)
        assert llm is not None
    finally:
        reset_resolver(token)


def test_llm_resolver_error_cases():
    # Uninitialized ContextVar
    with pytest.raises(LlmConfigError, match="not initialized"):
        get_llm(StepKey.TRIAGE)

    resolver = LlmResolver(
        steps={
            StepKey.TRIAGE: StepSelection(
                step_key=StepKey.TRIAGE,
                provider_id="nonexistent",
                model_id="bad",
                temperature=None,
                max_output_tokens=None,
                is_default=False,
            ),
            StepKey.DIAGNOSTICS: StepSelection(
                step_key=StepKey.DIAGNOSTICS,
                provider_id="anthropic",
                model_id="claude-sonnet-5-5",
                temperature=None,
                max_output_tokens=None,
                is_default=False,
            ),
        },
        credentials={},
    )

    with pytest.raises(LlmConfigError, match="Unknown pipeline step"):
        resolver.get_llm("unknown_step")

    with pytest.raises(LlmConfigError, match="unknown provider"):
        resolver.get_llm(StepKey.TRIAGE)

    with pytest.raises(LlmConfigError, match="No valid credential"):
        resolver.get_llm(StepKey.DIAGNOSTICS)


def test_friendly_error_formats_auth_and_generic_exceptions():
    auth_msg = friendly_error(RuntimeError("HTTP 401 Unauthorized: invalid api_key"))
    assert "Authentication with the LLM provider failed" in auth_msg

    other_msg = friendly_error(ValueError("timeout connecting"))
    assert other_msg == "ValueError: timeout connecting"
