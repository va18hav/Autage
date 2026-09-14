from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from services.http.schemas.auth import (
    AuthStatusResponse,
    LoginRequest,
    RegisterRequest,
    UserOut,
)


def test_register_request_validation():
    req = RegisterRequest(
        name="Ada Lovelace",
        username="ada",
        password="strong-password-123",
    )
    assert req.username == "ada"

    # Password shorter than 8 chars is rejected
    with pytest.raises(ValidationError):
        RegisterRequest(name="Ada", username="ada", password="short")


def test_login_and_auth_status_schemas():
    login = LoginRequest(username="ada", password="pw")
    assert login.username == "ada"

    user_out = UserOut(
        id=uuid4(),
        username="ada",
        name="Ada Lovelace",
        created_at=datetime.now(timezone.utc),
    )
    status = AuthStatusResponse(
        initialized=True,
        authenticated=True,
        user=user_out,
    )
    assert status.user is not None
    assert status.user.username == "ada"
