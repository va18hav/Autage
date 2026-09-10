from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4
from services.db.models.credentials import Credential, LlmStepConfig
from services.db.models.incident import Incident, IncidentStatus, IncidentStep
from services.db.models.runbooks import Runbook, RunbookSection
from services.db.models.user import User

class FakeScalarResult:
    def __init__(self, items: list[Any]):
        self._items = items

    def all(self) -> list[Any]:
        return list(self._items)


class FakeExecuteResult:
    def __init__(self, rows: list[Any]):
        self._rows = rows

    def scalar_one(self) -> Any:
        return self._rows[0]

    def scalar_one_or_none(self) -> Any:
        return self._rows[0] if self._rows else None

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self._rows)


class InMemoryAsyncSession:
    """In-memory SQLAlchemy AsyncSession stand-in for deterministic unit & route tests."""

    def __init__(self):
        self.users: dict[UUID, User] = {}
        self.incidents: dict[UUID, Incident] = {}
        self.incident_steps: dict[UUID, IncidentStep] = {}
        self.runbooks: dict[UUID, Runbook] = {}
        self.credentials: dict[str, Credential] = {}
        self.llm_steps: dict[str, LlmStepConfig] = {}
        self.closed: bool = False

    def add(self, obj: Any) -> None:
        now = datetime.now(timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        obj.updated_at = now

        if isinstance(obj, User):
            if obj.id is None:
                obj.id = uuid4()
            self.users[obj.id] = obj
        elif isinstance(obj, Incident):
            if obj.id is None:
                obj.id = uuid4()
            if not hasattr(obj, "steps") or obj.steps is None:
                obj.steps = []
            self.incidents[obj.id] = obj
        elif isinstance(obj, IncidentStep):
            if obj.id is None:
                obj.id = uuid4()
            self.incident_steps[obj.id] = obj
        elif isinstance(obj, Runbook):
            if obj.id is None:
                obj.id = uuid4()
            if not hasattr(obj, "sections") or obj.sections is None:
                obj.sections = []
            self.runbooks[obj.id] = obj
        elif isinstance(obj, RunbookSection):
            if obj.id is None:
                obj.id = uuid4()
            if obj.runbook is not None:
                obj.runbook_id = obj.runbook.id
                if obj not in obj.runbook.sections:
                    obj.runbook.sections.append(obj)
        elif isinstance(obj, Credential):
            self.credentials[obj.purpose] = obj
        elif isinstance(obj, LlmStepConfig):
            self.llm_steps[obj.step_key] = obj

    async def get(self, model: Any, pk: Any) -> Any:
        if isinstance(pk, str):
            try:
                pk_uuid = UUID(pk)
            except ValueError:
                pk_uuid = None
        else:
            pk_uuid = pk

        if model is User:
            return self.users.get(pk_uuid)
        if model is Incident:
            return self.incidents.get(pk_uuid)
        if model is IncidentStep:
            return self.incident_steps.get(pk_uuid)
        if model is Runbook:
            return self.runbooks.get(pk_uuid)
        if model is Credential:
            return self.credentials.get(pk)
        if model is LlmStepConfig:
            return self.llm_steps.get(pk)
        return None

    async def delete(self, obj: Any) -> None:
        if isinstance(obj, Incident):
            self.incidents.pop(obj.id, None)
        elif isinstance(obj, Runbook):
            self.runbooks.pop(obj.id, None)
        elif isinstance(obj, Credential):
            self.credentials.pop(obj.purpose, None)
        elif isinstance(obj, LlmStepConfig):
            self.llm_steps.pop(obj.step_key, None)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def close(self) -> None:
        self.closed = True

    async def refresh(self, obj: Any) -> None:
        now = datetime.now(timezone.utc)
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now

    @asynccontextmanager
    async def factory(self):
        yield self

    async def execute(self, stmt: Any) -> FakeExecuteResult:
        sql = str(stmt)
        params = stmt.compile().params

        # UPDATE statements
        if sql.startswith("UPDATE incidents"):
            inc_id = params.get("id_1")
            if isinstance(inc_id, str):
                inc_id = UUID(inc_id)
            inc = self.incidents.get(inc_id)
            if inc is not None:
                if "status" in params:
                    inc.status = params["status"]
                if "title" in params:
                    inc.title = params["title"]
                if "recommended_steps" in params:
                    inc.recommended_steps = params["recommended_steps"]
            return FakeExecuteResult([])

        if sql.startswith("UPDATE incident_steps"):
            step_id = params.get("id_1")
            step = self.incident_steps.get(step_id)
            if step is not None:
                if "status" in params:
                    step.status = params["status"]
                if "output_data" in params:
                    step.output_data = params["output_data"]
                if "error_message" in params:
                    step.error_message = params["error_message"]
            return FakeExecuteResult([])

        # User queries
        if "FROM users" in sql:
            if "count(" in sql.lower():
                return FakeExecuteResult([len(self.users)])
            username = next(iter(params.values()), None)
            matches = [u for u in self.users.values() if u.username == username]
            return FakeExecuteResult(matches)

        # Incident queries
        if "FROM incidents" in sql:
            if "WHERE incidents.fingerprint =" in sql:
                fp = params.get("fingerprint_1")
                matches = [
                    inc
                    for inc in self.incidents.values()
                    if inc.fingerprint == fp
                    and inc.status in (IncidentStatus.PENDING, IncidentStatus.TRIAGING)
                ]
                return FakeExecuteResult(matches)
            if "WHERE incidents.id =" in sql:
                inc_id = next(iter(params.values()), None)
                inc = self.incidents.get(inc_id)
                return FakeExecuteResult([inc] if inc else [])
            ordered = sorted(
                self.incidents.values(),
                key=lambda i: i.created_at,
                reverse=True,
            )
            return FakeExecuteResult(ordered)

        # Runbook section join queries
        if "FROM runbook_sections JOIN runbooks" in sql:
            title = params.get("title_1")
            order_index = params.get("order_index_1")
            for rb in self.runbooks.values():
                if rb.title == title:
                    for sec in rb.sections:
                        if sec.order_index == order_index:
                            return FakeExecuteResult([sec])
            return FakeExecuteResult([])

        # Runbook queries
        if "FROM runbooks" in sql:
            if "count(" in sql.lower():
                return FakeExecuteResult([len(self.runbooks)])
            if "WHERE runbooks.title =" in sql:
                title = params.get("title_1")
                service = params.get("service_1")
                matches = [
                    rb
                    for rb in self.runbooks.values()
                    if rb.title == title and rb.service == service
                ]
                return FakeExecuteResult(matches)
            if "WHERE runbooks.id =" in sql:
                rb_id = next(iter(params.values()), None)
                rb = self.runbooks.get(rb_id)
                return FakeExecuteResult([rb] if rb else [])
            ordered = sorted(
                self.runbooks.values(),
                key=lambda r: r.created_at,
                reverse=True,
            )
            return FakeExecuteResult(ordered)

        # LlmStepConfig queries
        if "FROM llm_step_configs" in sql:
            return FakeExecuteResult(list(self.llm_steps.values()))

        # Credential queries
        if "FROM credentials" in sql:
            ordered = sorted(self.credentials.values(), key=lambda c: c.purpose)
            return FakeExecuteResult(ordered)

        return FakeExecuteResult([])
