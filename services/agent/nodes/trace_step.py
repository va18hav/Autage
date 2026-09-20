import json
from typing import Any, Awaitable, Callable, Dict



# LangGraph node signature: takes the state dict, returns a dict of state updates.
# Keyword-only args (e.g. injected config) are accepted and forwarded untouched.
NodeFunc = Callable[..., Awaitable[Dict[str, Any]]]


def _jsonable(value: Any) -> Any:
    """Round-trip through json.dumps so JSONB columns never blow up on
    enums / datetimes / pydantic objects a node might put in its I/O."""
    return json.loads(json.dumps(value, default=str))
