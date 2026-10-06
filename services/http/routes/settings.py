from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.agent.llm import registry, StepKey
from services.agent.llm.registry import (
    UnknownProviderError,
    get_provider,
    missing_credential_fields,
)
from services.agent.llm.resolver import DEFAULT_STEP_MODELS, STEP_LABELS
from services.config import settings
from services.db.database import get_db_session
from services.db.models.credentials import Credential, LlmStepConfig
from services.http.schemas.settings import (
    CatalogResponse,
    CredentialOut,
    CredentialPayloadIn,
    ProviderOut,
    StepConfigIn,
    StepConfigOut,
    StepConfigsResponse,
    StepKeyOut,
    TestCredentialResponse,
)
from services.secrets.store import SecretStore

router = APIRouter(prefix="/settings", tags=["Settings"])

_ENV_CREDENTIAL_FALLBACK = {
    "google": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


async def _provider_configured(db: AsyncSession, provider_id: str) -> bool:
    """A provider is usable when a credential row exists or the legacy env var
    is set (self-hosters who never opened Settings still work)."""
    row = await db.get(Credential, provider_id)
    return bool(row) or bool(getattr(settings, _ENV_CREDENTIAL_FALLBACK.get(provider_id, ""), None))


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


@router.put(
    "/llm",
    response_model=StepConfigsResponse,
    summary="Upsert per-step LLM selection",
)
async def put_llm_settings(
    payload: List[StepConfigIn],
    db: AsyncSession = Depends(get_db_session),
):
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload must contain at least one step configuration",
        )

    seen: set[str] = set()
    for item in payload:
        if item.step_key in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate step in payload: {item.step_key}",
            )
        seen.add(item.step_key)
        _ensure_step_key(item.step_key)
        _validate_selection(item.provider_id, item.model_id)

    for item in payload:
        row = await db.get(LlmStepConfig, item.step_key)
        if row is None:
            row = LlmStepConfig(step_key=item.step_key)
            db.add(row)
        row.provider_id = item.provider_id
        row.model_id = item.model_id
        row.temperature = item.temperature
        row.max_output_tokens = item.max_output_tokens

    await db.commit()
    return await get_llm_settings(db)


@router.delete(
    "/llm/{step_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset a step to its built-in default",
)
async def reset_step_config(step_key: str, db: AsyncSession = Depends(get_db_session)):
    _ensure_step_key(step_key)
    row = await db.get(LlmStepConfig, step_key)
    if row:
        await db.delete(row)
        await db.commit()


def _ensure_step_key(step_key: str) -> None:
    if step_key not in [s.value for s in StepKey]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown step key '{step_key}'. Valid: {[s.value for s in StepKey]}",
        )


def _build_preview(spec, fields: dict[str, str]) -> str:
    """Masked fingerprint for the UI: secret fields show first 3 + last 4,
    non-secret fields (e.g. a base URL) are shown as-is."""
    for field in spec.credential_fields:
        value = fields.get(field.name)
        if not value:
            continue
        if not field.is_secret:
            return value
        if len(value) > 10:
            return f"{value[:3]}…{value[-4:]}"
        return "••••"
    return "••••"


def _validate_selection(provider_id: str, model_id: str) -> None:
    try:
        spec = get_provider(provider_id)
    except UnknownProviderError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider '{provider_id}'",
        )
    if model_id not in {m.id for m in spec.models}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model '{model_id}' is not registered for provider '{provider_id}'",
        )


# ── Credential management ─────────────────────────────────────────────────────

@router.get(
    "/credentials",
    response_model=List[CredentialOut],
    summary="Stored credentials (masked — payloads are never returned)",
)
async def list_credentials(db: AsyncSession = Depends(get_db_session)):
    return (await db.execute(select(Credential).order_by(Credential.purpose))).scalars().all()


@router.put(
    "/credentials/{purpose}",
    response_model=CredentialOut,
    summary="Create or rotate the credential for `purpose`",
)
async def upsert_credential(
    purpose: str,
    payload: CredentialPayloadIn,
    db: AsyncSession = Depends(get_db_session),
):
    try:
        spec = get_provider(purpose)
    except UnknownProviderError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown credential purpose '{purpose}'",
        )

    fields = {k: v.strip() for k, v in payload.fields.items() if v and v.strip()}
    missing = missing_credential_fields(spec, fields)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required field(s): {', '.join(missing)}",
        )

    preview = _build_preview(spec, fields)
    await SecretStore.save(purpose, fields, preview)
    return await db.get(Credential, purpose)


@router.delete(
    "/credentials/{purpose}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a stored credential",
)
async def delete_credential(purpose: str, db: AsyncSession = Depends(get_db_session)):
    deleted = await SecretStore.delete(purpose)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No credential stored for '{purpose}'",
        )


@router.post(
    "/credentials/{purpose}/test",
    response_model=TestCredentialResponse,
    summary="Store-less connectivity check against the provider",
)
async def test_credential(
    purpose: str,
    payload: CredentialPayloadIn,
    db: AsyncSession = Depends(get_db_session),
):
    """Verify the supplied credential fields by making a tiny live call.
    Nothing is persisted — used by the 'Verify' button during setup."""
    try:
        spec = get_provider(purpose)
    except UnknownProviderError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown credential purpose '{purpose}'",
        )

    fields = {k: v.strip() for k, v in payload.fields.items() if v and v.strip()}
    missing = missing_credential_fields(spec, fields)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required field(s): {', '.join(missing)}",
        )

    model = spec.create(
        credential=fields,
        model_id=spec.models[0].id,
        temperature=0,
        max_output_tokens=None,
    )
    try:
        await model.ainvoke("Say OK.")
    except Exception as exc:
        return TestCredentialResponse(
            ok=False,
            provider=spec.id,
            model=spec.models[0].id,
            message=f"Provider rejected the credential: {exc.__class__.__name__}",
        )

    return TestCredentialResponse(
        ok=True,
        provider=spec.id,
        model=spec.models[0].id,
        message="Credential verified — the provider accepted the request.",
    )
