import enum

class IncidentStatus(str, enum.Enum):
    PENDING = "PENDING"
    TRIAGING = "TRIAGING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
