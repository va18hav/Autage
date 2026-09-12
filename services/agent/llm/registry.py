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
