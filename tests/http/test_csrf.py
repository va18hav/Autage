import pytest

from services.http.auth import COOKIE_NAME
from services.http.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME


@pytest.mark.anyio
async def test_auth_status_issues_a_dashboard_readable_csrf_cookie(api_client):
    response = await api_client.get("/auth/status")

    assert response.status_code == 200
    set_cookie_headers = [
        header
        for header in response.headers.get_list("set-cookie")
        if header.startswith(f"{CSRF_COOKIE_NAME}=")
    ]
    assert len(set_cookie_headers) == 1

    cookie_header = set_cookie_headers[0].lower()
    assert "httponly" not in cookie_header
    assert "samesite=lax" in cookie_header
    assert "path=/" in cookie_header
    assert api_client.cookies.get(CSRF_COOKIE_NAME)


@pytest.mark.anyio
async def test_protected_write_requires_a_matching_csrf_token(authed_client):
    client = authed_client
    client.auto_csrf = False

    missing = await client.post(
        "/incidents/simulate",
        json={"scenario": "oomkill"},
    )
    assert missing.status_code == 403
    assert missing.json()["detail"] == "CSRF validation failed."

    wrong = await client.post(
        "/incidents/simulate",
        headers={CSRF_HEADER_NAME: "wrong-token"},
        json={"scenario": "oomkill"},
    )
    assert wrong.status_code == 403

    token = client.cookies.get(CSRF_COOKIE_NAME)
    assert token
    accepted = await client.post(
        "/incidents/simulate",
        headers={CSRF_HEADER_NAME: token},
        json={"scenario": "oomkill"},
    )
    assert accepted.status_code == 202


@pytest.mark.anyio
async def test_safe_reads_do_not_require_a_csrf_token(authed_client):
    authed_client.auto_csrf = False

    response = await authed_client.get("/incidents")

    assert response.status_code == 200


@pytest.mark.anyio
async def test_logout_requires_csrf_and_clears_both_cookies(authed_client):
    client = authed_client
    client.auto_csrf = False

    blocked = await client.post("/auth/logout")
    assert blocked.status_code == 403
    assert client.cookies.get(COOKIE_NAME)
    assert client.cookies.get(CSRF_COOKIE_NAME)

    client.auto_csrf = True
    logout = await client.post("/auth/logout")

    assert logout.status_code == 204
    assert client.cookies.get(COOKIE_NAME) is None
    assert client.cookies.get(CSRF_COOKIE_NAME) is None


@pytest.mark.anyio
async def test_login_rotates_the_csrf_token(authed_client):
    client = authed_client
    previous_token = client.cookies.get(CSRF_COOKIE_NAME)
    assert previous_token

    assert (await client.post("/auth/logout")).status_code == 204
    login = await client.post(
        "/auth/login",
        json={"username": "ada", "password": "super-secret-password"},
    )

    assert login.status_code == 200
    new_token = client.cookies.get(CSRF_COOKIE_NAME)
    assert new_token
    assert new_token != previous_token
