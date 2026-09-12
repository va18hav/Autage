import pytest

import services.secrets.store as store_mod
from services.secrets.store import SecretStore
from tests.conftest import InMemoryAsyncSession


@pytest.mark.anyio
async def test_secret_store_crud_lifecycle(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(store_mod, "async_session_factory", session.factory)

    # 1. Missing credential returns None / False
    assert await SecretStore.fetch_payload("openai") is None
    assert await SecretStore.exists("openai") is False
    assert await SecretStore.delete("openai") is False

    # 2. Save new credential
    row = await SecretStore.save(
        purpose="openai",
        payload={"api_key": "sk-proj-1234567890"},
        preview="sk-…7890",
    )
    assert row.purpose == "openai"
    assert row.preview == "sk-…7890"
    assert "sk-proj-1234567890" not in row.encrypted_payload

    # 3. Exists, fetch_payload (decrypted via decorator), and list_all
    assert await SecretStore.exists("openai") is True
    decrypted = await SecretStore.fetch_payload("openai")
    assert decrypted == {"api_key": "sk-proj-1234567890"}

    # 4. Update existing credential in place
    await SecretStore.save(
        purpose="openai",
        payload={"api_key": "sk-proj-rotated9999"},
        preview="sk-…9999",
    )
    assert await SecretStore.fetch_payload("openai") == {"api_key": "sk-proj-rotated9999"}

    all_rows = await SecretStore.list_all()
    assert len(all_rows) == 1
    assert all_rows[0].preview == "sk-…9999"

    # 5. Delete credential
    assert await SecretStore.delete("openai") is True
    assert await SecretStore.exists("openai") is False
