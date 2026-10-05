import pytest

@pytest.mark.anyio
async def test_health_endpoint(api_client):
    res = await api_client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
