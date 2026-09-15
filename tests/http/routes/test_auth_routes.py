import pytest


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
        json={"name": "   ", "username": "   ", "password": "valid-password-123"},
    )
    assert blank_res.status_code == 400

    # 3. Register first admin user -> 201 + cookie set
    reg_res = await api_client.post(
        "/auth/register",
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
