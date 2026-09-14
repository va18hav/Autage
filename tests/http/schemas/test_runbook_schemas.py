import pytest
from pydantic import ValidationError

from services.http.schemas.runbook import RunbookCreate, RunbookSectionIn


def test_runbook_section_in_strips_whitespace_and_rejects_blank_heading():
    sec = RunbookSectionIn(
        heading="  Rollback Procedure  ",
        content="  kubectl rollout undo  ",
        order_index=0,
    )
    assert sec.heading == "Rollback Procedure"
    assert sec.content == "kubectl rollout undo"

    with pytest.raises(ValidationError):
        RunbookSectionIn(heading="   ", content="valid", order_index=0)


def test_runbook_create_normalizes_optional_fields():
    rb = RunbookCreate(
        title="  Auth Service Runbook  ",
        service="   ",
        triggers=["  OOMKilled ", "", "   ", "CrashLoopBackOff"],
        raw_content="# Auth Service",
        sections=[
            RunbookSectionIn(heading="Mitigation", content="Restart pod", order_index=0)
        ],
    )
    assert rb.title == "Auth Service Runbook"
    assert rb.service is None
    assert rb.triggers == ["OOMKilled", "CrashLoopBackOff"]

    with pytest.raises(ValidationError):
        RunbookCreate(title="   ", raw_content="# Empty", sections=[])
