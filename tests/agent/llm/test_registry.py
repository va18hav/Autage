from services.agent.llm.registry import get_provider, missing_credential_fields

def test_missing_credential_fields_and_needs_credential():
    openai = get_provider("openai")
    assert openai.needs_credential is True
    assert missing_credential_fields(openai, None) == ["api_key"]
    assert missing_credential_fields(openai, {"api_key": "   "}) == ["api_key"]
    assert missing_credential_fields(openai, {"api_key": "sk-123"}) == []

    ollama = get_provider("ollama")
    assert ollama.needs_credential is False
    assert missing_credential_fields(ollama, None) == []


def test_provider_factories_construct_chat_models():
    for pid, creds in [
        ("google", {"api_key": "test-google-key"}),
        ("openai", {"api_key": "sk-test-openai"}),
        ("anthropic", {"api_key": "sk-ant-test"}),
        ("openrouter", {"api_key": "sk-or-test"}),
        ("ollama", {"base_url": "http://localhost:11434"}),
    ]:
        spec = get_provider(pid)
        model = spec.create(creds, spec.models[0].id, 0.2, 512)
        assert model is not None
