import pytest

import services.http.app as app_mod
from services.http.app import app, lifespan
from tests.conftest import FakeRedis


@pytest.mark.anyio
async def test_health_endpoint_checks_postgres_and_redis(api_client):
    res = await api_client.get("/health")
    assert res.status_code == 200
    assert res.json() == {
        "status": "ok",
        "postgres": "ok",
        "redis": "ok",
    }


@pytest.mark.anyio
async def test_health_endpoint_reports_postgres_failure(api_env, api_client, monkeypatch):
    session, _ = api_env

    async def _fail(_statement):
        raise ConnectionError("postgres unavailable")

    monkeypatch.setattr(session, "execute", _fail)

    res = await api_client.get("/health")

    assert res.status_code == 503
    assert res.json() == {
        "status": "degraded",
        "postgres": "error",
        "redis": "ok",
    }


@pytest.mark.anyio
async def test_health_endpoint_reports_redis_failure(api_env, api_client, monkeypatch):
    _, redis_client = api_env

    async def _fail():
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(redis_client, "ping", _fail)

    res = await api_client.get("/health")

    assert res.status_code == 503
    assert res.json() == {
        "status": "degraded",
        "postgres": "ok",
        "redis": "error",
    }


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
