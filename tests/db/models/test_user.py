from services.db.models.user import User


def test_user_model_definition():
    assert User.__tablename__ == "users"
    user = User(
        username="admin",
        name="Admin User",
        password_hash="$2b$12$abcdefghijklmnopqrstuv",
    )
    assert user.username == "admin"
    assert user.name == "Admin User"
