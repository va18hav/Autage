import asyncio
import json
import secrets
import ssl
import urllib.error
import urllib.request
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.agent.llm import registry, StepKey
from services.agent.llm import discovery as model_discovery
from services.agent.llm.discovery import DiscoveryError
from services.agent.llm.registry import (
    UnknownProviderError,
    get_provider,
    missing_credential_fields,
)
from services.agent.llm.resolver import DEFAULT_STEP_MODELS, STEP_LABELS
from services.db.database import get_db_session
from services.db.models.credentials import Credential, LlmStepConfig
from services.http.schemas.settings import (
    CatalogResponse,
    CredentialOut,
    CredentialPayloadIn,
    KubernetesConfigIn,
    KubernetesConfigOut,
    ProviderOut,
    StepConfigIn,
    StepConfigOut,
    StepConfigsResponse,
    StepKeyOut,
    TestCredentialResponse,
    WebhookSecretOut,
)
from services.secrets.store import SecretStore

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
        models = catalog_entry["models"]
        models_source = "static"

        # With a stored credential, ask the provider what it currently serves
        # so retired model IDs never reach the UI. Static list = fallback.
        payload = await SecretStore.fetch_payload(spec.id)
        if payload:
            try:
                live = await model_discovery.list_models_live(spec, payload)
                models = [
                    {"id": m.id, "label": m.label, "tier": m.tier} for m in live
                ]
                models_source = "live"
            except DiscoveryError:
                pass  # keep fallback list; user can still use "Verify connection" to diagnose

        providers.append(
            ProviderOut(
                id=spec.id,
                display_name=spec.display_name,
                models=models,
                credential_fields=catalog_entry["credential_fields"],
                credential_configured=await _provider_configured(db, spec.id),
                credential_preview=await _credential_preview(db, spec.id),
                models_source=models_source,
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
        await _validate_selection(item.provider_id, item.model_id)

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


async def _validate_selection(provider_id: str, model_id: str) -> None:
    try:
        spec = get_provider(provider_id)
    except UnknownProviderError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider '{provider_id}'",
        )

    static_ids = {m.id for m in spec.models}
    if model_id in static_ids:
        return

    # Not in the static fallback — accept it only if the provider currently
    # serves it (model lists discovered live after the key was saved).
    payload = await SecretStore.fetch_payload(provider_id)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Model '{model_id}' is not registered for provider '{provider_id}' "
                "(and no API key is stored — add one in Settings → Integrations)"
            ),
        )
    try:
        live = await model_discovery.list_models_live(spec, payload)
    except DiscoveryError:
        # Provider listing unreachable right now — stay permissive so a saved
        # configuration can still be rotated; a bad ID surfaces at run time.
        return
    if model_id not in {m.id for m in live}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Model '{model_id}' is not available for provider '{provider_id}'. "
                "Verify the connection in Settings → Integrations and pick a "
                "current model."
            ),
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
    # Credential changed → next catalog read should re-discover models live.
    model_discovery.invalidate(purpose)
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
    model_discovery.invalidate(purpose)


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
    """Verify the supplied credential fields by listing the provider's current
    models live (free, no token cost). Nothing is persisted — used by the
    'Verify' button during setup. Success also proves the key works, because
    model-listing endpoints require valid authentication."""
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

    try:
        models = await model_discovery.list_models_live(spec, fields, force_refresh=True)
    except DiscoveryError as exc:
        detail = str(exc)
        if "HTTP 401" in detail or "HTTP 403" in detail:
            message = "Provider rejected the credential (401/403) — check the API key."
        elif "HTTP 4" in detail[:12]:
            message = f"Provider rejected the request: {detail[:200]}"
        else:
            message = f"Could not reach the provider's model list ({detail[:200]})."
        return TestCredentialResponse(
            ok=False,
            provider=spec.id,
            model=None,
            message=message,
        )

    if not models:
        return TestCredentialResponse(
            ok=False,
            provider=spec.id,
            model=None,
            message="Provider returned an empty model list — the key may be valid but restricted.",
        )

    return TestCredentialResponse(
        ok=True,
        provider=spec.id,
        model=None,
        message=(
            f"Credential verified — {len(models)} models available "
            "(model list fetched live; no token cost)."
        ),
    )


# ── Monitoring webhook secret ─────────────────────────────────────────────────

@router.get(
    "/webhook",
    response_model=WebhookSecretOut,
    summary="Fetch the current monitoring webhook secret state from the credentials table",
)
async def get_webhook_secret(db: AsyncSession = Depends(get_db_session)):
    row = await db.get(Credential, WEBHOOK_SECRET_PURPOSE)
    if row is None:
        return WebhookSecretOut(
            configured=False,
            secret=None,
            preview=None,
            updated_at=None,
        )

    payload = await SecretStore.fetch_payload(WEBHOOK_SECRET_PURPOSE)
    secret_val = (payload or {}).get("secret")
    return WebhookSecretOut(
        configured=bool(secret_val),
        secret=secret_val,
        preview=row.preview,
        updated_at=row.updated_at,
    )


@router.post(
    "/webhook/secret",
    response_model=WebhookSecretOut,
    summary="Generate a new webhook signing secret and store it encrypted in the credentials table",
)
async def generate_webhook_secret():
    secret_val = f"whsec_{secrets.token_hex(24)}"
    preview = f"{secret_val[:9]}…{secret_val[-4:]}"
    row = await SecretStore.save(
        WEBHOOK_SECRET_PURPOSE,
        {"secret": secret_val},
        preview,
    )
    return WebhookSecretOut(
        configured=True,
        secret=secret_val,
        preview=row.preview,
        updated_at=row.updated_at,
    )


# ── Kubernetes cluster connection ─────────────────────────────────────────────

def _mask_k8s_token(token: str) -> str:
    t = token.strip()
    if len(t) > 12:
        return f"{t[:6]}…{t[-4:]}"
    return "••••"


def _probe_k8s_api(server_url: str, token: str, ca_cert: str) -> TestCredentialResponse:
    base = server_url.strip().rstrip("/")
    if not base.startswith("https://"):
        return TestCredentialResponse(
            ok=False,
            provider="kubernetes",
            model=None,
            message=(
                "Cluster API URL must use https:// — TLS verification of the "
                "connection is mandatory and cannot be disabled."
            ),
        )
    ca_cert = ca_cert.strip()
    if "-----BEGIN CERTIFICATE-----" not in ca_cert:
        return TestCredentialResponse(
            ok=False,
            provider="kubernetes",
            model=base,
            message=(
                "The cluster CA certificate is missing or malformed — it must be "
                "the PEM block starting with '-----BEGIN CERTIFICATE-----' "
                "(copy `certificate-authority-data` decoded from your kubeconfig)."
            ),
        )

    url = f"{base}/api/v1/namespaces?limit=1"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token.strip()}",
            "Accept": "application/json",
        },
        method="GET",
    )
    # TLS is always verified against the cluster's own CA certificate — the
    # python equivalent of `curl --cacert <kind_ca.pem>`. There is no
    # skip-verification path.
    ctx = ssl.create_default_context(cadata=ca_cert)

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if body.get("kind") == "NamespaceList":
                return TestCredentialResponse(
                    ok=True,
                    provider="kubernetes",
                    model=base,
                    message=(
                        "Connected to Kubernetes API server with verified TLS "
                        "certificate; read access confirmed."
                    ),
                )
            return TestCredentialResponse(
                ok=True,
                provider="kubernetes",
                model=base,
                message=f"Connected to cluster ({resp.status}).",
            )
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return TestCredentialResponse(
                ok=False,
                provider="kubernetes",
                model=base,
                message=(
                    f"Cluster rejected the ServiceAccount token (HTTP {exc.code}). "
                    "Re-paste the token exactly as printed — it is one long JWT "
                    "(starts with 'eyJ', no quotes, no spaces). If the token expired, "
                    "create a new one with: kubectl create token <sa-name> -n default"
                ),
            )
        return TestCredentialResponse(
            ok=False,
            provider="kubernetes",
            model=base,
            message=f"Kubernetes API returned HTTP {exc.code}.",
        )
    except Exception as exc:
        err_name = exc.__class__.__name__
        if isinstance(exc, ssl.SSLError) or "certificate" in str(exc).lower():
            message = (
                "TLS verification failed — the server's certificate was not signed "
                "by the CA certificate you provided. Check that you copied the "
                "CA of THIS cluster (each cluster has its own)."
            )
        else:
            message = f"Could not reach cluster at {base} ({err_name})."
            try:
                from urllib.parse import urlparse

                if (urlparse(base).hostname or "") in ("127.0.0.1", "localhost", "0.0.0.0", "0.0.0.0:6443"):
                    message += (
                        " If Autage itself runs in Docker (docker compose), the cluster is not "
                        "reachable at that address from inside the containers — use "
                        "https://host.docker.internal:<port> instead."
                    )
            except Exception:
                pass
        return TestCredentialResponse(
            ok=False,
            provider="kubernetes",
            model=base,
            message=message,
        )


@router.get(
    "/kubernetes",
    response_model=KubernetesConfigOut,
    summary="Fetch the stored Kubernetes cluster connection state",
)
async def get_kubernetes_config(db: AsyncSession = Depends(get_db_session)):
    row = await db.get(Credential, KUBERNETES_PURPOSE)
    if row is None:
        return KubernetesConfigOut(
            configured=False,
            server_url=None,
            token_preview=None,
            ca_configured=False,
            updated_at=None,
        )

    payload = await SecretStore.fetch_payload(KUBERNETES_PURPOSE) or {}
    server_url = payload.get("server_url")
    token = payload.get("token") or ""
    ca_cert = payload.get("ca_cert") or ""
    return KubernetesConfigOut(
        configured=bool(server_url and token and ca_cert),
        server_url=server_url,
        token_preview=_mask_k8s_token(token) if token else row.preview,
        ca_configured=bool("-----BEGIN CERTIFICATE-----" in ca_cert),
        updated_at=row.updated_at,
    )


@router.put(
    "/kubernetes",
    response_model=KubernetesConfigOut,
    summary="Save or update the Kubernetes cluster connection (API URL, read-only ServiceAccount token, CA certificate)",
)
async def save_kubernetes_config(payload: KubernetesConfigIn):
    server_url = payload.server_url.strip().rstrip("/")
    token = payload.token.strip()
    ca_cert = payload.ca_cert.strip()
    if not server_url.startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cluster API URL must use https:// — TLS verification of the "
                "connection is mandatory and cannot be disabled."
            ),
        )
    if "-----BEGIN CERTIFICATE-----" not in ca_cert:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The cluster CA certificate is required and must be a PEM block "
                "starting with '-----BEGIN CERTIFICATE-----'."
            ),
        )

    token_preview = _mask_k8s_token(token)
    ca_preview = "CA certificate stored"
    row = await SecretStore.save(
        KUBERNETES_PURPOSE,
        {"server_url": server_url, "token": token, "ca_cert": ca_cert},
        preview=f"{server_url} ({token_preview}) — {ca_preview}",
    )
    return KubernetesConfigOut(
        configured=True,
        server_url=server_url,
        token_preview=token_preview,
        ca_configured=True,
        updated_at=row.updated_at,
    )


@router.delete(
    "/kubernetes",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect the stored Kubernetes cluster",
)
async def delete_kubernetes_config():
    deleted = await SecretStore.delete(KUBERNETES_PURPOSE)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Kubernetes cluster configuration found",
        )


@router.post(
    "/kubernetes/test",
    response_model=TestCredentialResponse,
    summary="Verify connectivity and read permissions against the Kubernetes API server",
)
async def test_kubernetes_config(payload: KubernetesConfigIn):
    return await asyncio.to_thread(
        _probe_k8s_api,
        payload.server_url,
        payload.token,
        payload.ca_cert,
    )
