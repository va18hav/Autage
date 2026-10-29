from typing import Any

from fastapi import Request

AUTH_RATE_LIMIT_ATTEMPTS = 5
AUTH_RATE_LIMIT_WINDOW_SECONDS = 15 * 60


class RateLimitBackendError(RuntimeError):
    """Raised when the Redis-backed rate limiter cannot be used."""


def client_ip(request: Request) -> str:
    """Return the direct peer address.

    Forwarded headers are intentionally ignored until a trusted reverse proxy
    is configured; accepting them now would let clients spoof their IP.
    """
    return request.client.host if request.client else "unknown"


def login_rate_limit_key(ip: str) -> str:
    return f"auth:login:ip:{ip}"


def setup_rate_limit_key(ip: str) -> str:
    return f"auth:setup:ip:{ip}"


def password_reset_rate_limit_key(ip: str) -> str:
    return f"auth:password-reset:ip:{ip}"


def _redis(request: Request) -> Any:
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise RateLimitBackendError("Redis is not configured")
    return redis


async def retry_after(redis: Any, key: str) -> int | None:
    """Return the remaining block time, or None when another attempt is allowed."""
    try:
        raw_count = await redis.get(key)
        if raw_count is None:
            return None

        attempts = int(raw_count)
        if attempts < AUTH_RATE_LIMIT_ATTEMPTS:
            return None

        ttl = int(await redis.ttl(key))
        if ttl < 0:
            # Self-heal a counter that lost its expiry before it can persist.
            await redis.expire(key, AUTH_RATE_LIMIT_WINDOW_SECONDS, nx=True)
            ttl = AUTH_RATE_LIMIT_WINDOW_SECONDS
        return max(ttl, 1)
    except Exception as exc:
        raise RateLimitBackendError("Could not read login rate limit") from exc


async def record_failure(redis: Any, key: str) -> None:
    try:
        attempts = await redis.incr(key)
        if int(attempts) == 1:
            await redis.expire(
                key,
                AUTH_RATE_LIMIT_WINDOW_SECONDS,
                nx=True,
            )
    except Exception as exc:
        raise RateLimitBackendError("Could not record login failure") from exc


async def clear_failures(redis: Any, key: str) -> None:
    try:
        await redis.delete(key)
    except Exception as exc:
        raise RateLimitBackendError("Could not clear login failures") from exc


def get_rate_limit_redis(request: Request) -> Any:
    return _redis(request)
