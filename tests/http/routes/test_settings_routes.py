import pytest

@pytest.mark.anyio
async def test_provider_catalog_and_llm_step_settings(authed_client):
    # 1. Provider catalog lists all 5 providers and 4 pipeline steps
    cat_res = await authed_client.get("/settings/providers")
    assert cat_res.status_code == 200
    provider_ids = {p["id"] for p in cat_res.json()["providers"]}
    assert provider_ids == {"google", "openai", "anthropic", "openrouter", "ollama"}
    assert len(cat_res.json()["steps"]) == 4

    # 2. Empty payload or duplicate step keys rejected with 400
    assert (await authed_client.put("/settings/llm", json=[])).status_code == 400
    dup_steps = await authed_client.put(
        "/settings/llm",
        json=[
            {"step_key": "triage", "provider_id": "openai", "model_id": "gpt-4o-mini"},
            {"step_key": "triage", "provider_id": "google", "model_id": "gemini-2.5-flash"},
        ],
    )
    assert dup_steps.status_code == 400

    # 3. Unknown provider or unknown model rejected with 400
    assert (
        await authed_client.put(
            "/settings/llm",
            json=[{"step_key": "triage", "provider_id": "unknown", "model_id": "m"}],
        )
    ).status_code == 400
    assert (
        await authed_client.put(
            "/settings/llm",
            json=[{"step_key": "triage", "provider_id": "openai", "model_id": "bad"}],
        )
    ).status_code == 400

    # 4. Valid step configuration saved and reset
    put_res = await authed_client.put(
        "/settings/llm",
        json=[
            {
                "step_key": "triage",
                "provider_id": "anthropic",
                "model_id": "claude-sonnet-4",
                "temperature": 0.1,
            }
        ],
    )
    assert put_res.status_code == 200
    triage_step = next(s for s in put_res.json()["steps"] if s["step_key"] == "triage")
    assert triage_step["provider_id"] == "anthropic"
    assert triage_step["is_default"] is False

    del_res = await authed_client.delete("/settings/llm/triage")
    assert del_res.status_code == 204

    # Unknown step key on reset returns 404
    assert (await authed_client.delete("/settings/llm/nonexistent")).status_code == 404
