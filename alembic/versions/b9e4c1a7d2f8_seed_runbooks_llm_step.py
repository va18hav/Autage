"""seed the runbooks LLM step from investigation

Revision ID: b9e4c1a7d2f8
Revises: f2a7c9d4e6b1
Create Date: 2026-11-05 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b9e4c1a7d2f8'
down_revision: Union[str, Sequence[str], None] = 'f2a7c9d4e6b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Give existing installs a working model for the new runbook step.

    Runbook selection is now LLM-backed. Copy an existing step selection
    (investigation first, then triage or diagnosis) so upgrades do not silently
    fall back to a provider the operator may not have configured. New installs
    configure all steps through onboarding.
    """
    op.execute(
        """
        INSERT INTO llm_step_configs (
            step_key,
            provider_id,
            model_id,
            temperature,
            max_output_tokens,
            credential_purpose
        )
        SELECT
            'runbooks',
            provider_id,
            model_id,
            temperature,
            max_output_tokens,
            credential_purpose
        FROM llm_step_configs
        WHERE step_key IN ('investigate', 'triage', 'diagnose')
        ORDER BY CASE step_key
            WHEN 'investigate' THEN 0
            WHEN 'triage' THEN 1
            ELSE 2
        END
        LIMIT 1
        ON CONFLICT (step_key) DO NOTHING
        """
    )


def downgrade() -> None:
    """Remove the runbook step configuration."""
    op.execute(
        """
        DELETE FROM llm_step_configs
        WHERE step_key = 'runbooks'
        """
    )
