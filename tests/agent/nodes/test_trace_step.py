import pytest
from services.agent.nodes.trace_step import traced_step

def test_traced_step_rejects_sync_function():
    with pytest.raises(TypeError, match="requires an async node function"):
        @traced_step("sync_node")
        def sync_fn(state):  # type: ignore[arg-type]
            return state
