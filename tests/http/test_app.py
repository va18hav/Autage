import pytest

import services.http.app as app_mod
from services.http.app import app, lifespan
from tests.conftest import FakeRedis


@pytest.mark.anyio
async def test_health_endpoint(api_client):
    res = await api_client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_app_lifespan_initializes_and_closes_redis(monkeypatch):
    fake_redis = FakeRedis()

    monkeypatch.setattr(
        app_mod.redis,
        "from_url",
        lambda *_args, **_kwargs: fake_redis,
    )

    async with lifespan(app):
        assert app.state.redis is fake_redis
        assert fake_redis.closed is False

    assert fake_redis.closed is True
