from uuid import uuid4
import pytest

@pytest.mark.anyio
async def test_simulate_list_detail_and_delete_incidents(api_env, authed_client):
    session, pool = api_env

    # 1. Simulate all supported scenarios
    for scenario in ("oomkill", "crashloop", "db_pool", "gateway_504"):
        res = await authed_client.post("/incidents/simulate", json={"scenario": scenario})
        assert res.status_code == 202
        assert res.json()["status"] == "PENDING"

    assert len(pool.enqueued) == 4

    # 2. List incidents
    list_res = await authed_client.get("/incidents")
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 4

    target_id = items[0]["id"]

    # 3. Detail endpoint
    detail_res = await authed_client.get(f"/incidents/{target_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == target_id

    # 4. Delete incident
    del_res = await authed_client.delete(f"/incidents/{target_id}")
    assert del_res.status_code == 204

    # 5. Unknown incident returns 404 on GET, stream, and DELETE
    missing_id = uuid4()
    assert (await authed_client.get(f"/incidents/{missing_id}")).status_code == 404
    assert (await authed_client.get(f"/incidents/{missing_id}/stream")).status_code == 404
    assert (await authed_client.delete(f"/incidents/{missing_id}")).status_code == 404
