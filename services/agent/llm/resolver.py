"""Per-run LLM resolution: which provider/model each pipeline step uses.

The worker loads one LlmResolver per incident run (two tiny queries), then the
resolver is installed for the duration of the run and every agent node calls
`get_llm(step_key)` — no node knows about concrete provider SDKs.
"""

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
