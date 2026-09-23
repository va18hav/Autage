import pytest
from pydantic import ValidationError
from services.http.schemas.auth import RegisterRequest

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
