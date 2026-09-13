from services.agent.llm.registry import get_provider

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
