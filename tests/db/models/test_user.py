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
    constraint_names = {c.name for c in User.__table__.constraints}
    assert "uq_users_single_instance" in constraint_names
    assert "ck_users_single_instance_key" in constraint_names
