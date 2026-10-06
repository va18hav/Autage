import functools
import inspect
import json
from typing import Any, Awaitable, Callable, Dict

from sqlalchemy import update

from services.db.database import async_session_factory
from services.db.models.incident import IncidentStep, StepStatus

# LangGraph node signature: takes the state dict, returns a dict of state updates.
# Keyword-only args (e.g. injected config) are accepted and forwarded untouched.
NodeFunc = Callable[..., Awaitable[Dict[str, Any]]]


def _jsonable(value: Any) -> Any:
    """Round-trip through json.dumps so JSONB columns never blow up on
    enums / datetimes / pydantic objects a node might put in its I/O."""
    return json.loads(json.dumps(value, default=str))


def traced_step(step_name: str) -> Callable[[NodeFunc], NodeFunc]:
    """Factory: bind a step_name to the returned decorator."""

    def decorator(func: NodeFunc) -> NodeFunc:
        if not inspect.iscoroutinefunction(func):
            raise TypeError(
                f"@traced_step requires an async node function, got sync '{func.__name__}'. "
                "Make the node async."
            )

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            # First positional arg is the LangGraph state (it contains incident_id)
            state: Dict[str, Any] = args[0] if args else kwargs["state"]
            incident_id = state["incident_id"]

            # 1. Insert the step as RUNNING and capture its generated ID
            async with async_session_factory() as db:
                step = IncidentStep(
                    incident_id=incident_id,
                    step_name=step_name,
                    status=StepStatus.RUNNING,
                    input_data=_jsonable(state),
                )
                db.add(step)
                await db.commit()
                await db.refresh(step)
                step_id = step.id

            try:
                # 2. Run the actual node body
                output = await func(*args, **kwargs)

                # 3. Mark COMPLETED and store the node's output
                async with async_session_factory() as db:
                    await db.execute(
                        update(IncidentStep)
                        .where(IncidentStep.id == step_id)
                        .values(
                            status=StepStatus.COMPLETED,
                            output_data=_jsonable(output),
                        )
                    )
                    await db.commit()

                return output

            except Exception as e:
                # 4. Mark FAILED with the error message, then re-raise
                #    (exception still propagates to LangGraph for retries/logging)
                async with async_session_factory() as db:
                    await db.execute(
                        update(IncidentStep)
                        .where(IncidentStep.id == step_id)
                        .values(
                            status=StepStatus.FAILED,
                            error_message=str(e),
                        )
                    )
                    await db.commit()
                raise

        # Keep LangGraph-compatible metadata
        wrapper.__name__ = f"traced_{step_name}"
        return wrapper  # type: ignore[return-value]

    return decorator
