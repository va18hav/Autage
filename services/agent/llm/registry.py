"""Model catalog and factory for every LLM provider Autage can use.

This is the ONLY place that knows about concrete chat-model SDKs. Nodes
resolve models through services.agent.llm.resolver instead of importing
provider classes, so adding a provider is a change to this file alone.
"""

from dataclasses import dataclass
from typing import Callable, Literal

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
