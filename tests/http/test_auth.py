from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from services.db.models.user import User
from services.http.auth import (
    COOKIE_NAME,
    clear_auth_cookie,
    create_access_token,
    decode_access_token,
    get_current_user,
    hash_password,
    resolve_optional_user,
    set_auth_cookie,
    verify_password,
)
from tests.conftest import InMemoryAsyncSession


def _make_request_with_cookies(cookies: dict[str, str]) -> Request:
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items()).encode()
    scope = {
        "type": "http",
        "headers": [(b"cookie", cookie_header)] if cookie_header else [],
    }
    return Request(scope)


def test_password_hash_and_verify():
    pw = "correct-horse-battery-staple"
    hashed = hash_password(pw)

    assert hashed != pw
    assert verify_password(pw, hashed) is True
    assert verify_password("wrong-password", hashed) is False
    assert verify_password(pw, "not-a-valid-bcrypt-hash") is False


def test_jwt_create_and_decode_roundtrip():
    uid = uuid4()
    token = create_access_token(uid, "sre_admin")
    claims = decode_access_token(token)

    assert claims is not None
    assert claims["sub"] == str(uid)
    assert claims["username"] == "sre_admin"
    assert "exp" in claims
    assert "iat" in claims
    assert decode_access_token("tampered.jwt.token") is None


def test_set_and_clear_auth_cookie():
    resp = Response()
    set_auth_cookie(resp, "sample-jwt-token")
    set_cookie_header = resp.headers.get("set-cookie", "")
    assert f"{COOKIE_NAME}=sample-jwt-token" in set_cookie_header
    assert "HttpOnly" in set_cookie_header

    clear_resp = Response()
    clear_auth_cookie(clear_resp)
    clear_header = clear_resp.headers.get("set-cookie", "")
    assert f'{COOKIE_NAME}=""' in clear_header or "Max-Age=0" in clear_header


@pytest.mark.anyio
async def test_resolve_optional_user_and_get_current_user():
    db = InMemoryAsyncSession()
    user = User(id=uuid4(), username="ada", name="Ada", password_hash="hash")
    db.add(user)

    # No cookie -> None / 401
    empty_req = _make_request_with_cookies({})
    assert await resolve_optional_user(empty_req, db) is None
    with pytest.raises(HTTPException) as exc:
        await get_current_user(empty_req, db)
    assert exc.value.status_code == 401

    # Malformed UUID in JWT sub -> None
    bad_sub_token = create_access_token("not-a-uuid", "ada")  # type: ignore[arg-type]
    bad_sub_req = _make_request_with_cookies({COOKIE_NAME: bad_sub_token})
    assert await resolve_optional_user(bad_sub_req, db) is None

    # Valid JWT for existing user -> returns User
    valid_token = create_access_token(user.id, user.username)
    valid_req = _make_request_with_cookies({COOKIE_NAME: valid_token})
    resolved = await get_current_user(valid_req, db)
    assert resolved.id == user.id
