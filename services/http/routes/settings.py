from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.agent.llm import registry, StepKey
from services.agent.llm.resolver import DEFAULT_STEP_MODELS, STEP_LABELS
from services.db.database import get_db_session
from services.db.models.credentials import Credential, LlmStepConfig
from services.http.schemas.settings import CatalogResponse, ProviderOut, StepConfigOut, StepConfigsResponse, StepKeyOut

router = APIRouter(prefix="/settings", tags=["Settings"])

WEBHOOK_SECRET_PURPOSE = "webhook_secret"
KUBERNETES_PURPOSE = "kubernetes"

_ENV_CREDENTIAL_FALLBACK = {
    "google": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


async def _provider_configured(db: AsyncSession, provider_id: str) -> bool:
    """A provider is configured when a credential row exists in the DB."""
    row = await db.get(Credential, provider_id)
    return bool(row)


# ── Provider catalog ──────────────────────────────────────────────────────────

@router.get(
    "/providers",
    response_model=CatalogResponse,
    summary="Registered LLM providers, their models, and configured state",
)
async def get_provider_catalog(db: AsyncSession = Depends(get_db_session)):
    providers = []
    for spec in registry.PROVIDERS.values():
        catalog_entry = registry.catalog_entry(spec)
        providers.append(
            ProviderOut(
                id=spec.id,
                display_name=spec.display_name,
                models=catalog_entry["models"],
                credential_fields=catalog_entry["credential_fields"],
                credential_configured=await _provider_configured(db, spec.id),
                credential_preview=await _credential_preview(db, spec.id),
            )
        )

    steps = [StepKeyOut(key=key, label=STEP_LABELS[key]) for key in StepKey]
    return CatalogResponse(providers=providers, steps=steps)


async def _credential_preview(db: AsyncSession, purpose: str) -> Optional[str]:
    credential = await db.get(Credential, purpose)
    return credential.preview if credential else None


# ── Per-step model configs ────────────────────────────────────────────────────

@router.get(
    "/llm",
    response_model=StepConfigsResponse,
    summary="Per-step LLM selection (defaults where unconfigured)",
)
async def get_llm_settings(db: AsyncSession = Depends(get_db_session)):
    rows = {
        row.step_key: row
        for row in (await db.execute(select(LlmStepConfig))).scalars().all()
    }

    steps = []
    for key in StepKey:
        row = rows.get(key)
        if row is not None:
            steps.append(
                StepConfigOut(
                    step_key=key,
                    provider_id=row.provider_id,
                    model_id=row.model_id,
                    temperature=row.temperature,
                    max_output_tokens=row.max_output_tokens,
                    is_default=False,
                    credential_configured=await _provider_configured(db, row.provider_id),
                )
            )
        else:
            provider_id, model_id = DEFAULT_STEP_MODELS[key]
            steps.append(
                StepConfigOut(
                    step_key=key,
                    provider_id=provider_id,
                    model_id=model_id,
                    temperature=None,
                    max_output_tokens=None,
                    is_default=True,
                    credential_configured=await _provider_configured(db, provider_id),
                )
            )

    return StepConfigsResponse(steps=steps)
