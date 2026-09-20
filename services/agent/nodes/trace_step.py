from typing import Any, Awaitable, Callable, Dict



# LangGraph node signature: takes the state dict, returns a dict of state updates.
# Keyword-only args (e.g. injected config) are accepted and forwarded untouched.
NodeFunc = Callable[..., Awaitable[Dict[str, Any]]]
