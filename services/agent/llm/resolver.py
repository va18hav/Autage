"""Per-run LLM resolution: which provider/model each pipeline step uses.

The worker loads one LlmResolver per incident run (two tiny queries), then the
resolver is installed for the duration of the run and every agent node calls
`get_llm(step_key)` — no node knows about concrete provider SDKs.
"""

from dataclasses import dataclass
from enum import Enum




class LlmConfigError(RuntimeError):
    """A user-fixable configuration problem (missing provider credential,
    unknown provider/model). Message is safe to surface in incident errors."""


class StepKey(str, Enum):
    TRIAGE = "triage"
    DIAGNOSTICS = "diagnostics"
    RUNBOOKS = "runbooks"
    RECOMMENDATIONS = "recommendations"


STEP_LABELS: dict[str, str] = {
    StepKey.TRIAGE: "Triage",
    StepKey.DIAGNOSTICS: "Diagnostics (log planning + summary)",
    StepKey.RUNBOOKS: "Runbook reasoning",
    StepKey.RECOMMENDATIONS: "Recommended steps",
}

# Legacy bridge: a provider whose key only lives in .env still works even
# though credentials are DB-only going forward. DB rows take precedence.
_ENV_CREDENTIAL_FALLBACK = {
    "google": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def _env_credential(provider_id: str) -> str | None:
    from services.config import settings

    env_name = _ENV_CREDENTIAL_FALLBACK.get(provider_id)
    if not env_name:
        return None
    # pydantic-settings loads .env into `settings`, not os.environ
    value = getattr(settings, env_name, None) or ""
    return str(value).strip() or None

# Behavior-preserving defaults (what the nodes were hard-coded to before).
# Override via the Settings API — rows in llm_step_configs replace these.
DEFAULT_STEP_MODELS: dict[str, tuple[str, str]] = {
    step_key: ("google", "gemini-3.7-flash") for step_key in StepKey
}


@dataclass(frozen=True)
class StepSelection:
    step_key: str
    provider_id: str
    model_id: str
    temperature: float | None
    max_output_tokens: int | None
    # True when this step has no DB row and is using the built-in default
    is_default: bool


class LlmResolver:
    def __init__(
        self,
        steps: dict[str, StepSelection],
        credentials: dict[str, dict],
    ):
        self._steps = steps
        self._credentials = credentials
