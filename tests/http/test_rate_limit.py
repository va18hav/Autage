import time

import pytest

from services.http.rate_limit import (
    AUTH_RATE_LIMIT_ATTEMPTS,
    AUTH_RATE_LIMIT_WINDOW_SECONDS,
    record_failure,
    retry_after,
)
from tests.conftest import FakeRedis


@pytest.mark.anyio
async def test_rate_limit_counts_failures_and_scopes_them_by_key():
    redis_client = FakeRedis()
    first_key = "auth:login:ip:192.0.2.10"
    second_key = "auth:login:ip:192.0.2.11"

    for _ in range(AUTH_RATE_LIMIT_ATTEMPTS):
        await record_failure(redis_client, first_key)

    remaining = await retry_after(redis_client, first_key)
    assert remaining is not None
    assert 0 < remaining <= AUTH_RATE_LIMIT_WINDOW_SECONDS
    assert await retry_after(redis_client, second_key) is None


@pytest.mark.anyio
async def test_rate_limit_expires_without_manual_cleanup():
    redis_client = FakeRedis()
    key = "auth:login:ip:192.0.2.10"

    for _ in range(AUTH_RATE_LIMIT_ATTEMPTS):
        await record_failure(redis_client, key)

    redis_client.rate_expires[key] = time.monotonic() - 1

    assert await retry_after(redis_client, key) is None
    assert key not in redis_client.rate_counts


@pytest.mark.anyio
async def test_rate_limit_self_heals_a_counter_without_expiry():
    redis_client = FakeRedis()
    key = "auth:login:ip:192.0.2.10"
    redis_client.rate_counts[key] = AUTH_RATE_LIMIT_ATTEMPTS

    remaining = await retry_after(redis_client, key)

    assert remaining == AUTH_RATE_LIMIT_WINDOW_SECONDS
    assert key in redis_client.rate_expires
