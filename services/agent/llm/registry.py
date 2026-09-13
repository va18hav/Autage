"""Model catalog and factory for every LLM provider Autage can use.

This is the ONLY place that knows about concrete chat-model SDKs. Nodes
resolve models through services.agent.llm.resolver instead of importing
provider classes, so adding a provider is a change to this file alone.
"""

from dataclasses import dataclass
from typing import Any, Callable, Literal

from langchain_core.language_models.chat_models import BaseChatModel

ModelTier = Literal["fast", "balanced", "frontier"]


@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    tier: ModelTier


@dataclass(frozen=True)
class CredentialField:
    """One entry a user supplies for this provider (e.g. api_key, base_url)."""

    name: str
    label: str
    is_secret: bool = True
    required: bool = True
    # Used to prefill / document optional fields (e.g. Ollama's local port)
    default: str | None = None


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    display_name: str
    credential_fields: tuple[CredentialField, ...]
    models: tuple[ModelSpec, ...]
    # Builds the chat model. `credential` is the decrypted payload dict
    # (None for providers that need no credential, e.g. local Ollama).
    create: Callable[[dict | None, str, float | None, int | None], BaseChatModel]

    @property
    def needs_credential(self) -> bool:
        return any(f.required for f in self.credential_fields)


class UnknownProviderError(KeyError):
    pass


def _apply(
    kwargs: dict,
    temperature: float | None,
    max_output_tokens: int | None,
    temperature_field: str = "temperature",
    max_tokens_field: str = "max_tokens",
) -> dict:
    if temperature is not None:
        kwargs[temperature_field] = temperature
    if max_output_tokens is not None:
        kwargs[max_tokens_field] = max_output_tokens
    return kwargs


# ── Provider factories ────────────────────────────────────────────────────────

def _create_google(
    credential: dict | None, model_id: str, temperature: float | None,
    max_output_tokens: int | None,
) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    kwargs = {"model": model_id, "google_api_key": credential["api_key"]}
    return ChatGoogleGenerativeAI(
        **_apply(kwargs, temperature, max_output_tokens, max_tokens_field="max_output_tokens")
    )


def _create_openai(
    credential: dict | None, model_id: str, temperature: float | None,
    max_output_tokens: int | None,
) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    kwargs = {"model": model_id, "api_key": credential["api_key"]}
    return ChatOpenAI(**_apply(kwargs, temperature, max_output_tokens))


def _create_anthropic(
    credential: dict | None, model_id: str, temperature: float | None,
    max_output_tokens: int | None,
) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    kwargs = {"model": model_id, "api_key": credential["api_key"]}
    # Anthropic requires an explicit max token budget; default to 4096.
    kwargs["max_tokens"] = max_output_tokens or 4096
    if temperature is not None:
        kwargs["temperature"] = temperature
    return ChatAnthropic(**kwargs)


def _create_openrouter(
    credential: dict | None, model_id: str, temperature: float | None,
    max_output_tokens: int | None,
) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    kwargs = {
        "model": model_id,
        "api_key": credential["api_key"],
        "base_url": "https://openrouter.ai/api/v1",
    }
    return ChatOpenAI(**_apply(kwargs, temperature, max_output_tokens))


def _create_ollama(
    credential: dict | None, model_id: str, temperature: float | None,
    max_output_tokens: int | None,
) -> BaseChatModel:
    from langchain_ollama import ChatOllama

    base_url = (credential or {}).get("base_url") or "http://localhost:11434"
    kwargs = {"model": model_id, "base_url": base_url}
    return ChatOllama(
        **_apply(kwargs, temperature, max_output_tokens, max_tokens_field="num_predict")
    )


# ── Registry definition ───────────────────────────────────────────────────────

_API_KEY = CredentialField(name="api_key", label="API Key")

PROVIDERS: dict[str, ProviderSpec] = {
    "google": ProviderSpec(
        id="google",
        display_name="Google Gemini",
        credential_fields=(_API_KEY,),
        models=(
            ModelSpec("gemini-3.7-flash", "Gemini 3.7 Flash", "fast"),
            ModelSpec("gemini-2.5-flash", "Gemini 2.5 Flash", "fast"),
            ModelSpec("gemini-2.5-pro", "Gemini 2.5 Pro", "frontier"),
        ),
        create=_create_google,
    ),
    "openai": ProviderSpec(
        id="openai",
        display_name="OpenAI",
        credential_fields=(_API_KEY,),
        models=(
            ModelSpec("gpt-4o-mini", "GPT-4o mini", "fast"),
            ModelSpec("gpt-4.1-mini", "GPT-4.1 mini", "balanced"),
            ModelSpec("gpt-4.1", "GPT-4.1", "frontier"),
        ),
        create=_create_openai,
    ),
    "anthropic": ProviderSpec(
        id="anthropic",
        display_name="Anthropic",
        credential_fields=(_API_KEY,),
        models=(
            ModelSpec("claude-3-5-haiku-latest", "Claude 3.5 Haiku", "fast"),
            ModelSpec("claude-sonnet-4", "Claude Sonnet 4", "balanced"),
            ModelSpec("claude-opus-4", "Claude Opus 4", "frontier"),
        ),
        create=_create_anthropic,
    ),
    "openrouter": ProviderSpec(
        id="openrouter",
        display_name="OpenRouter",
        credential_fields=(_API_KEY,),
        models=(
            ModelSpec("openai/gpt-4o-mini", "GPT-4o mini", "fast"),
            ModelSpec("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet", "balanced"),
            ModelSpec("google/gemini-2.5-pro", "Gemini 2.5 Pro", "frontier"),
        ),
        create=_create_openrouter,
    ),
    "ollama": ProviderSpec(
        id="ollama",
        display_name="Ollama (local)",
        credential_fields=(
            CredentialField(
                name="base_url",
                label="Ollama Server URL",
                is_secret=False,
                required=False,
                default="http://localhost:11434",
            ),
        ),
        models=(
            ModelSpec("llama3.2", "Llama 3.2", "fast"),
            ModelSpec("qwen2.5:7b", "Qwen 2.5 7B", "balanced"),
            ModelSpec("deepseek-r1:14b", "DeepSeek R1 14B", "frontier"),
        ),
        create=_create_ollama,
    ),
}


def get_provider(provider_id: str) -> ProviderSpec:
    spec = PROVIDERS.get(provider_id)
    if spec is None:
        raise UnknownProviderError(
            f"Unknown LLM provider '{provider_id}'. Known providers: {sorted(PROVIDERS)}"
        )
    return spec


def missing_credential_fields(spec: ProviderSpec, credential: dict | None) -> list[str]:
    """Names of required credential fields absent (or empty) from `credential`."""
    credential = credential or {}
    return [
        field.name
        for field in spec.credential_fields
        if field.required and not str(credential.get(field.name) or "").strip()
    ]


def catalog_entry(spec: ProviderSpec) -> dict[str, Any]:
    """Serializable single-provider entry for the API."""
    return {
        "id": spec.id,
        "display_name": spec.display_name,
        "models": [
            {"id": m.id, "label": m.label, "tier": m.tier} for m in spec.models
        ],
        "credential_fields": [
            {
                "name": f.name,
                "label": f.label,
                "is_secret": f.is_secret,
                "required": f.required,
                "default": f.default,
            }
            for f in spec.credential_fields
        ],
    }


def catalog() -> list[dict[str, Any]]:
    """Serializable provider/model catalog for the API."""
    return [catalog_entry(spec) for spec in PROVIDERS.values()]
