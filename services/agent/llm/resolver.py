"""Per-run LLM resolution: which provider/model each pipeline step uses.

The worker loads one LlmResolver per incident run (two tiny queries), then the
resolver is installed for the duration of the run and every agent node calls
`get_llm(step_key)` — no node knows about concrete provider SDKs.
"""

from contextvars import ContextVar
from dataclasses import dataclass
from enum import Enum

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy import select

from services.agent.llm import registry
from services.db.database import async_session_factory
from services.db.models.credentials import LlmStepConfig
from services.secrets.store import SecretStore


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

    @classmethod
    async def load(cls) -> "LlmResolver":
        """Read step configs + credentials from the DB exactly once per run."""
        async with async_session_factory() as db:
            rows = (
                await db.execute(
                    select(LlmStepConfig).where(
                        LlmStepConfig.step_key.in_([s.value for s in StepKey])
                    )
                )
            ).scalars().all()

        # Store only decrypted payloads belonging to providers we can use
        credentials: dict[str, dict] = {}
        for provider_id in registry.PROVIDERS:
            payload = await SecretStore.fetch_payload(provider_id)
            if payload:
                credentials[provider_id] = payload
            else:
                env_key = _env_credential(provider_id)
                if env_key:
                    credentials[provider_id] = {"api_key": env_key}

        steps = {}
        for key in StepKey:
            row = next((r for r in rows if r.step_key == key), None)
            if row is not None:
                steps[key] = StepSelection(
                    step_key=key,
                    provider_id=row.provider_id,
                    model_id=row.model_id,
                    temperature=row.temperature,
                    max_output_tokens=row.max_output_tokens,
                    is_default=False,
                )
            else:
                provider_id, model_id = DEFAULT_STEP_MODELS[key]
                steps[key] = StepSelection(
                    step_key=key,
                    provider_id=provider_id,
                    model_id=model_id,
                    temperature=None,
                    max_output_tokens=None,
                    is_default=True,
                )

        return cls(steps=steps, credentials=credentials)

    def get_llm(self, step_key: str) -> BaseChatModel:
        """Build the chat model for a pipeline step (cheapest at first use)."""
        selection = self._steps.get(step_key)
        if selection is None:
            raise LlmConfigError(
                f"Unknown pipeline step '{step_key}'. Valid steps: "
                f"{[s.value for s in StepKey]}"
            )

        try:
            spec = registry.get_provider(selection.provider_id)
        except registry.UnknownProviderError as exc:
            raise LlmConfigError(
                f"Step '{step_key}' is configured to use unknown provider "
                f"'{selection.provider_id}'. Fix it in Settings → Model by step."
            ) from exc

        credential = self._credentials.get(spec.id)
        missing = registry.missing_credential_fields(spec, credential)
        if missing:
            raise LlmConfigError(
                f"No valid credential configured for provider '{spec.display_name}' "
                f"(\"{spec.id}\") — missing: {missing}. Add the key in Settings → Integrations."
            )

        return spec.create(
            credential=credential,
            model_id=selection.model_id,
            temperature=selection.temperature,
            max_output_tokens=selection.max_output_tokens,
        )

    def describe(self) -> dict[str, StepSelection]:
        return dict(self._steps)


def friendly_error(exc: BaseException, steps: dict[str, str] | None = None) -> str:
    """Best-effort human message when a run fails inside a provider SDK."""
    message = str(exc).lower()
    if any(marker in message for marker in ("401", "unauthorized", "api key", "api_key")):
        return (
            f"Authentication with the LLM provider failed ({exc.__class__.__name__}). "
            "Check the API key in Settings → Integrations."
        )
    return f"{exc.__class__.__name__}: {exc}"


_resolver: ContextVar[LlmResolver | None] = ContextVar("llm_resolver", default=None)


def set_resolver(resolver: LlmResolver):
    """Install the resolver for the current context (per incident run)."""
    return _resolver.set(resolver)


def reset_resolver(token) -> None:
    _resolver.reset(token)


def get_llm(step_key: str) -> BaseChatModel:
    """The single entry point agent nodes use to obtain their chat model."""
    resolver = _resolver.get()
    if resolver is None:
        raise LlmConfigError(
            "LLM resolver not initialized — call LlmResolver.load() and "
            "set_resolver() before running the agent graph."
        )
    return resolver.get_llm(step_key)
