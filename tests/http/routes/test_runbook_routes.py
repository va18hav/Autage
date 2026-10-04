from uuid import uuid4

import pytest


@pytest.mark.anyio
async def test_runbooks_create_idempotent_replace_get_and_delete(authed_client):
    payload = {
        "title": "PostgreSQL Connection Pool Exhaustion",
        "description": "Handle PgBouncer and max_connections saturation",
        "service": "postgres",
        "triggers": ["too many clients already"],
        "raw_content": "# Postgres\n## Terminate Idle\nSELECT pg_terminate_backend(pid);",
        "sections": [
            {"heading": "Verify Connections", "content": "Check pg_stat_activity", "order_index": 20},
            {"heading": "Terminate Idle", "content": "SELECT pg_terminate_backend(pid);", "order_index": 5},
        ],
    }

    # 1. Create runbook -> sections sorted by order_index and re-numbered 0..N-1
    create_res = await authed_client.post("/runbooks", json=payload)
    assert create_res.status_code == 201
    created = create_res.json()
    assert [s["heading"] for s in created["sections"]] == [
        "Terminate Idle",
        "Verify Connections",
    ]
    assert [s["order_index"] for s in created["sections"]] == [0, 1]

    # 2. Re-uploading same (title, service) replaces previous runbook
    updated_payload = {
        **payload,
        "description": "Updated description",
    }
    replace_res = await authed_client.post("/runbooks", json=updated_payload)
    assert replace_res.status_code == 201
    rb_id = replace_res.json()["id"]

    list_res = await authed_client.get("/runbooks")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1
    assert list_res.json()[0]["description"] == "Updated description"

    # 3. Get runbook detail
    detail_res = await authed_client.get(f"/runbooks/{rb_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["title"] == payload["title"]

    # 4. Delete runbook
    del_res = await authed_client.delete(f"/runbooks/{rb_id}")
    assert del_res.status_code == 204

    # 5. 404 on unknown runbook
    missing = uuid4()
    assert (await authed_client.get(f"/runbooks/{missing}")).status_code == 404
    assert (await authed_client.delete(f"/runbooks/{missing}")).status_code == 404
