import time

import pytest

from services.http.rate_limit import (
    AUTH_RATE_LIMIT_ATTEMPTS,
    AUTH_RATE_LIMIT_WINDOW_SECONDS,
    record_failure,
    retry_after,
)
from tests.conftest import FakeArqPool


@pytest.mark.anyio
async def test_rate_limit_counts_failures_and_scopes_them_by_key():
    pool = FakeArqPool()
    first_key = "auth:login:ip:192.0.2.10"
    second_key = "auth:login:ip:192.0.2.11"

    for _ in range(AUTH_RATE_LIMIT_ATTEMPTS):
        await record_failure(pool, first_key)

    remaining = await retry_after(pool, first_key)
    assert remaining is not None
    assert 0 < remaining <= AUTH_RATE_LIMIT_WINDOW_SECONDS
    assert await retry_after(pool, second_key) is None


@pytest.mark.anyio
async def test_rate_limit_expires_without_manual_cleanup():
    pool = FakeArqPool()
    key = "auth:login:ip:192.0.2.10"

    for _ in range(AUTH_RATE_LIMIT_ATTEMPTS):
        await record_failure(pool, key)

    pool.rate_expires[key] = time.monotonic() - 1

    assert await retry_after(pool, key) is None
    assert key not in pool.rate_counts


@pytest.mark.anyio
async def test_rate_limit_self_heals_a_counter_without_expiry():
    pool = FakeArqPool()
    key = "auth:login:ip:192.0.2.10"
    pool.rate_counts[key] = AUTH_RATE_LIMIT_ATTEMPTS

    remaining = await retry_after(pool, key)

    assert remaining == AUTH_RATE_LIMIT_WINDOW_SECONDS
    assert key in pool.rate_expires
