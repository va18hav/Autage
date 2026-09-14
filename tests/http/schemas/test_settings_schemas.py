import pytest
from pydantic import ValidationError

from services.http.schemas.settings import (
    CredentialPayloadIn,
    KubernetesConfigIn,
    StepConfigIn,
)


def test_step_config_in_bounds_validation():
    cfg = StepConfigIn(
        step_key="triage",
        provider_id="openai",
        model_id="gpt-4o-mini",
        temperature=0.5,
        max_output_tokens=2048,
    )
    assert cfg.temperature == 0.5

    # Temperature > 2.0 is invalid
    with pytest.raises(ValidationError):
        StepConfigIn(
            step_key="triage",
            provider_id="openai",
            model_id="gpt-4o-mini",
            temperature=3.5,
        )


def test_kubernetes_and_credential_payload_schemas():
    k8s = KubernetesConfigIn(
        server_url="https://kubernetes.default.svc:6443",
        token="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9",
    )
    assert k8s.server_url.startswith("https://")

    cred = CredentialPayloadIn(fields={"api_key": "sk-123"})
    assert cred.fields["api_key"] == "sk-123"
