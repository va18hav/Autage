import pytest
from pydantic import ValidationError
from services.http.schemas.runbook import RunbookSectionIn

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
