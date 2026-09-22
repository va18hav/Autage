from uuid import uuid4
from services.http.auth import create_access_token, decode_access_token, hash_password, verify_password

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
