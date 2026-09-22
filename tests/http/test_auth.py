from services.http.auth import hash_password, verify_password

def test_password_hash_and_verify():
    pw = "correct-horse-battery-staple"
    hashed = hash_password(pw)

    assert hashed != pw
    assert verify_password(pw, hashed) is True
    assert verify_password("wrong-password", hashed) is False
    assert verify_password(pw, "not-a-valid-bcrypt-hash") is False
