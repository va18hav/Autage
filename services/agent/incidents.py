from enum import Enum


class IncidentType(str, Enum):
    """Coarse label used for prompts and reporting, not tool selection."""

    CRASH_LOOP = "crash_loop"
    BAD_DEPLOYMENT = "bad_deployment"
    OTHER = "other"
