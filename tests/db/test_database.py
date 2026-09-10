import pytest

import services.db.database as db_mod
from tests.conftest import InMemoryAsyncSession


@pytest.mark.anyio
async def test_get_db_session_yields_and_closes_session(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(db_mod, "async_session_factory", session.factory)

    gen = db_mod.get_db_session()
    yielded = await gen.__anext__()
    assert yielded is session
    assert session.closed is False

    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()

    assert session.closed is True
