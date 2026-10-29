import pytest
from sqlalchemy.exc import IntegrityError

from services.config import settings
from tests.conftest import TEST_SETUP_TOKEN

SETUP_HEADERS = {"X-Autage-Setup-Token": TEST_SETUP_TOKEN}
REGISTER_PAYLOAD = {
    "name": "Ada Lovelace",
    "username": "ada",
    "password": "super-secret-password",
}


@pytest.mark.anyio
async def test_registration_requires_the_configured_setup_token(
    api_client,
    monkeypatch,
):
    missing = await api_client.post("/auth/register", json=REGISTER_PAYLOAD)
    assert missing.status_code == 401
    assert missing.json()["detail"] == "Invalid setup token."

    wrong = await api_client.post(
        "/auth/register",
        headers={"X-Autage-Setup-Token": "wrong-setup-token"},
        json=REGISTER_PAYLOAD,
    )
    assert wrong.status_code == 401

    monkeypatch.setattr(settings, "AUTAGE_SETUP_TOKEN", None)
    not_configured = await api_client.post(
        "/auth/register",
        headers=SETUP_HEADERS,
        json=REGISTER_PAYLOAD,
    )
    assert not_configured.status_code == 503
    assert "AUTAGE_SETUP_TOKEN" in not_configured.json()["detail"]

    status_res = await api_client.get("/auth/status")
    assert status_res.json()["initialized"] is False


@pytest.mark.anyio
async def test_registration_maps_single_user_race_to_forbidden(
    api_env,
    api_client,
    monkeypatch,
):
    session, _ = api_env

    async def _raise_integrity_error():
        raise IntegrityError("INSERT INTO users", {}, Exception("duplicate"))

    monkeypatch.setattr(session, "commit", _raise_integrity_error)

    response = await api_client.post(
        "/auth/register",
        headers=SETUP_HEADERS,
        json=REGISTER_PAYLOAD,
    )

    assert response.status_code == 403
    assert session.rolled_back is True


@pytest.mark.anyio
async def test_login_rate_limit_blocks_even_a_correct_password(authed_client):
    client = authed_client
    await client.post("/auth/logout")

    for _ in range(5):
        failed = await client.post(
            "/auth/login",
            json={"username": "ada", "password": "wrong-password"},
        )
        assert failed.status_code == 401

    blocked = await client.post(
        "/auth/login",
        json={"username": "ada", "password": "super-secret-password"},
    )

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


@pytest.mark.anyio
async def test_successful_login_clears_failure_counter(authed_client):
    client = authed_client
    await client.post("/auth/logout")

    for _ in range(4):
        failed = await client.post(
            "/auth/login",
            json={"username": "ada", "password": "wrong-password"},
        )
        assert failed.status_code == 401

    success = await client.post(
        "/auth/login",
        json={"username": "ada", "password": "super-secret-password"},
    )
    assert success.status_code == 200
    await client.post("/auth/logout")

    after_reset = await client.post(
        "/auth/login",
        json={"username": "ada", "password": "wrong-password"},
    )
    assert after_reset.status_code == 401


@pytest.mark.anyio
async def test_successful_registration_clears_setup_failure_counter(api_client):
    for _ in range(4):
        failed = await api_client.post(
            "/auth/register",
            headers={"X-Autage-Setup-Token": "wrong-setup-token"},
            json=REGISTER_PAYLOAD,
        )
        assert failed.status_code == 401

    registered = await api_client.post(
        "/auth/register",
        headers=SETUP_HEADERS,
        json=REGISTER_PAYLOAD,
    )
    assert registered.status_code == 201


@pytest.mark.anyio
async def test_setup_token_rate_limit_is_enforced(api_client):
    for _ in range(5):
        failed = await api_client.post(
            "/auth/register",
            headers={"X-Autage-Setup-Token": "wrong-setup-token"},
            json=REGISTER_PAYLOAD,
        )
        assert failed.status_code == 401

    blocked = await api_client.post(
        "/auth/register",
        headers=SETUP_HEADERS,
        json=REGISTER_PAYLOAD,
    )

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


@pytest.mark.anyio
async def test_unknown_user_gets_the_same_generic_login_failure(api_client):
    response = await api_client.post(
        "/auth/login",
        json={"username": "does-not-exist", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


@pytest.mark.anyio
async def test_login_fails_closed_when_rate_limit_backend_is_unavailable(
    api_env,
    api_client,
    monkeypatch,
):
    _, pool = api_env

    async def _unavailable(_key: str):
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(pool, "get", _unavailable)

    response = await api_client.post(
        "/auth/login",
        json={"username": "ada", "password": "super-secret-password"},
    )

    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"]


@pytest.mark.anyio
async def test_password_policy_requires_twelve_characters(api_client):
    response = await api_client.post(
        "/auth/register",
        headers=SETUP_HEADERS,
        json={
            "name": "Ada Lovelace",
            "username": "ada",
            "password": "short-pass",
        },
    )

    assert response.status_code == 422
    status_res = await api_client.get("/auth/status")
    assert status_res.json()["initialized"] is False


@pytest.mark.anyio
async def test_password_reset_enforces_the_password_policy(authed_client):
    response = await authed_client.post(
        "/auth/reset-password",
        headers=SETUP_HEADERS,
        json={
            "new_password": "short-pass",
            "confirm_password": "short-pass",
        },
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_password_reset_requires_the_setup_token(authed_client):
    client = authed_client
    await client.post("/auth/logout")

    missing = await client.post(
        "/auth/reset-password",
        json={
            "new_password": "new-secret-password",
            "confirm_password": "new-secret-password",
        },
    )
    assert missing.status_code == 401

    wrong = await client.post(
        "/auth/reset-password",
        headers={"X-Autage-Setup-Token": "wrong-setup-token"},
        json={
            "new_password": "new-secret-password",
            "confirm_password": "new-secret-password",
        },
    )
    assert wrong.status_code == 401

    still_old = await client.post(
        "/auth/login",
        json={"username": "ada", "password": "super-secret-password"},
    )
    assert still_old.status_code == 200


@pytest.mark.anyio
async def test_password_reset_updates_the_password(authed_client):
    client = authed_client
    await client.post("/auth/logout")

    response = await client.post(
        "/auth/reset-password",
        headers=SETUP_HEADERS,
        json={
            "new_password": "new-secret-password",
            "confirm_password": "new-secret-password",
        },
    )
    assert response.status_code == 204

    old_login = await client.post(
        "/auth/login",
        json={"username": "ada", "password": "super-secret-password"},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/auth/login",
        json={"username": "ada", "password": "new-secret-password"},
    )
    assert new_login.status_code == 200


@pytest.mark.anyio
async def test_password_reset_clears_login_failures(authed_client):
    client = authed_client
    await client.post("/auth/logout")

    for _ in range(4):
        failed = await client.post(
            "/auth/login",
            json={"username": "ada", "password": "wrong-password"},
        )
        assert failed.status_code == 401

    reset = await client.post(
        "/auth/reset-password",
        headers=SETUP_HEADERS,
        json={
            "new_password": "new-secret-password",
            "confirm_password": "new-secret-password",
        },
    )
    assert reset.status_code == 204

    login = await client.post(
        "/auth/login",
        json={"username": "ada", "password": "new-secret-password"},
    )
    assert login.status_code == 200


@pytest.mark.anyio
async def test_password_reset_rejects_mismatched_confirmation(authed_client):
    response = await authed_client.post(
        "/auth/reset-password",
        headers=SETUP_HEADERS,
        json={
            "new_password": "new-secret-password",
            "confirm_password": "different-password",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Passwords do not match."


@pytest.mark.anyio
async def test_password_reset_requires_an_initialized_instance(api_client):
    response = await api_client.post(
        "/auth/reset-password",
        headers=SETUP_HEADERS,
        json={
            "new_password": "new-secret-password",
            "confirm_password": "new-secret-password",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Instance is not initialized."


@pytest.mark.anyio
async def test_password_reset_fails_closed_without_a_configured_token(
    authed_client,
    monkeypatch,
):
    monkeypatch.setattr(settings, "AUTAGE_SETUP_TOKEN", None)

    response = await authed_client.post(
        "/auth/reset-password",
        headers=SETUP_HEADERS,
        json={
            "new_password": "new-secret-password",
            "confirm_password": "new-secret-password",
        },
    )

    assert response.status_code == 503
    assert "AUTAGE_SETUP_TOKEN" in response.json()["detail"]


@pytest.mark.anyio
async def test_password_reset_token_failures_are_rate_limited(authed_client):
    client = authed_client

    for _ in range(5):
        failed = await client.post(
            "/auth/reset-password",
            headers={"X-Autage-Setup-Token": "wrong-setup-token"},
            json={
                "new_password": "new-secret-password",
                "confirm_password": "new-secret-password",
            },
        )
        assert failed.status_code == 401

    blocked = await client.post(
        "/auth/reset-password",
        headers=SETUP_HEADERS,
        json={
            "new_password": "new-secret-password",
            "confirm_password": "new-secret-password",
        },
    )

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


@pytest.mark.anyio
async def test_auth_status_register_login_me_and_logout(api_client):
    # 1. Before setup: initialized=False, authenticated=False
    status_res = await api_client.get("/auth/status")
    assert status_res.status_code == 200
    assert status_res.json() == {
        "initialized": False,
        "authenticated": False,
        "user": None,
    }

    # 2. Blank username or name rejected with 400
    blank_res = await api_client.post(
        "/auth/register",
        headers=SETUP_HEADERS,
        json={"name": "   ", "username": "   ", "password": "valid-password-123"},
    )
    assert blank_res.status_code == 400

    # 3. Register first admin user -> 201 + cookie set
    reg_res = await api_client.post(
        "/auth/register",
        headers=SETUP_HEADERS,
        json={
            "name": "Ada Lovelace",
            "username": "  ADA  ",
            "password": "super-secret-password",
        },
    )
    assert reg_res.status_code == 201
    assert reg_res.json()["username"] == "ada"
    assert "autage_token" in api_client.cookies

    # 4. Second registration blocked with 403 Forbidden
    dup_res = await api_client.post(
        "/auth/register",
        headers=SETUP_HEADERS,
        json={
            "name": "Second User",
            "username": "second",
            "password": "super-secret-password",
        },
    )
    assert dup_res.status_code == 403

    # 5. /auth/me and /auth/status reflect authenticated user
    me_res = await api_client.get("/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "ada"

    status_authed = await api_client.get("/auth/status")
    assert status_authed.json()["initialized"] is True
    assert status_authed.json()["authenticated"] is True

    # 6. Logout clears session cookie
    logout_res = await api_client.post("/auth/logout")
    assert logout_res.status_code == 204
    api_client.cookies.clear()

    me_after_logout = await api_client.get("/auth/me")
    assert me_after_logout.status_code == 401

    # 7. Login with wrong password fails (401), valid password succeeds (200)
    bad_login = await api_client.post(
        "/auth/login",
        json={"username": "ada", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401

    ok_login = await api_client.post(
        "/auth/login",
        json={"username": "ADA", "password": "super-secret-password"},
    )
    assert ok_login.status_code == 200
    assert ok_login.json()["username"] == "ada"
