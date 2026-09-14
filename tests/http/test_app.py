import pytest

import services.http.app as app_mod
from services.http.app import app, lifespan
from tests.conftest import FakeArqPool


@pytest.mark.anyio
async def test_health_endpoint(api_client):
    res = await api_client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_app_lifespan_initializes_and_closes_arq_pool(monkeypatch):
    fake_pool = FakeArqPool()

    async def _fake_create_pool(_settings):
        return fake_pool

    monkeypatch.setattr(app_mod, "create_pool", _fake_create_pool)

    async with lifespan(app):
        assert app.state.arq_pool is fake_pool
        assert fake_pool.closed is False

    assert fake_pool.closed is True
