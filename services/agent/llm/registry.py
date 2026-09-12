"""Model catalog and factory for every LLM provider Autage can use.

This is the ONLY place that knows about concrete chat-model SDKs. Nodes
resolve models through services.agent.llm.resolver instead of importing
provider classes, so adding a provider is a change to this file alone.
"""

from dataclasses import dataclass
from typing import Literal


ModelTier = Literal["fast", "balanced", "frontier"]


@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    tier: ModelTier
