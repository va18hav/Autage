import json
from uuid import UUID, uuid4

import pytest

import services.http.routes.incident as incident_routes_mod
from services.db.models.incident import IncidentStatus


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


@pytest.mark.anyio
async def test_incident_sse_stream_completed_and_live_pubsub(api_env, authed_client, monkeypatch):
    session, pool = api_env
    monkeypatch.setattr(incident_routes_mod, "async_session_factory", session.factory)

    # Case 1: Incident already COMPLETED before stream opens
    sim1 = await authed_client.post("/incidents/simulate", json={"scenario": "oomkill"})
    inc1_id = sim1.json()["incident_id"]
    session.incidents[UUID(inc1_id)].status = IncidentStatus.COMPLETED
    session.incidents[UUID(inc1_id)].title = "OOMKill Resolved"

    stream1 = await authed_client.get(f"/incidents/{inc1_id}/stream")
    assert stream1.status_code == 200
    assert "incident_complete" in stream1.text
    assert "OOMKill Resolved" in stream1.text

    # Case 2: Live incident receives step_complete followed by incident_complete over Redis Pub/Sub
    sim2 = await authed_client.post("/incidents/simulate", json={"scenario": "db_pool"})
    inc2_id = sim2.json()["incident_id"]

    pool.pubsub_instance._messages = [
        {
            "type": "message",
            "data": json.dumps({"type": "step_complete", "node": "process_alert"}).encode(),
        },
        {
            "type": "message",
            "data": json.dumps({"type": "incident_complete", "status": "COMPLETED"}).encode(),
        },
    ]

    stream2 = await authed_client.get(f"/incidents/{inc2_id}/stream")
    assert stream2.status_code == 200
    assert "step_complete" in stream2.text
    assert "incident_complete" in stream2.text
    assert pool.pubsub_instance.closed is True
