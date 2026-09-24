import pytest
from pydantic import ValidationError
from services.http.schemas.settings import StepConfigIn

def test_step_config_in_bounds_validation():
    cfg = StepConfigIn(
        step_key="triage",
        provider_id="openai",
        model_id="gpt-4o-mini",
        temperature=0.5,
        max_output_tokens=2048,
    )
    assert cfg.temperature == 0.5

    # Temperature > 2.0 is invalid
    with pytest.raises(ValidationError):
        StepConfigIn(
            step_key="triage",
            provider_id="openai",
            model_id="gpt-4o-mini",
            temperature=3.5,
        )
