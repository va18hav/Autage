from services.db.models.credentials import Credential, LlmStepConfig


def test_credential_and_llm_step_config_models():
    assert Credential.__tablename__ == "credentials"
    assert LlmStepConfig.__tablename__ == "llm_step_configs"

    cred = Credential(
        purpose="openai",
        encrypted_payload="gAAAAAB...",
        preview="sk-…1234",
    )
    assert cred.purpose == "openai"

    cfg = LlmStepConfig(
        step_key="triage",
        provider_id="openai",
        model_id="gpt-4o-mini",
        temperature=0.2,
        max_output_tokens=1024,
        credential_purpose="openai",
    )
    assert cfg.step_key == "triage"
    assert cfg.provider_id == "openai"
