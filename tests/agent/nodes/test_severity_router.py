from uuid import uuid4

import pytest

import services.agent.nodes.trace_step as trace_step_mod
from services.agent.nodes.severity_router import (
    route_p1,
    route_p2,
    route_p3,
    severity_router,
)
from tests.conftest import InMemoryAsyncSession


@pytest.mark.anyio
async def test_severity_router_and_route_nodes(monkeypatch):
    session = InMemoryAsyncSession()
    monkeypatch.setattr(trace_step_mod, "async_session_factory", session.factory)

    assert severity_router({"severity": "P1"}) == "P1"
    assert severity_router({"severity": "P2"}) == "P2"
    assert severity_router({"severity": "P3"}) == "P3"

    state = {"incident_id": str(uuid4())}
    p1_out = await route_p1(state)
    p2_out = await route_p2(state)
    p3_out = await route_p3(state)

    assert "P1 CRITICAL" in p1_out["proposed_action"]
    assert "P2" in p2_out["proposed_action"]
    assert "P3" in p3_out["proposed_action"]
