"""rename LLM step keys to triage and diagnose

Revision ID: b7c9e1f2a3d4
Revises: f4a1c2d3e5b6
Create Date: 2026-10-29 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7c9e1f2a3d4'
down_revision: Union[str, Sequence[str], None] = 'f4a1c2d3e5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keep the diagnosis model choice and drop stages that no longer call an LLM."""
    op.execute(
        """
        UPDATE llm_step_configs AS target
        SET step_key = 'diagnose'
        WHERE target.step_key = 'recommendations'
          AND NOT EXISTS (
              SELECT 1
              FROM llm_step_configs AS existing
              WHERE existing.step_key = 'diagnose'
          )
        """
    )
    op.execute(
        """
        DELETE FROM llm_step_configs
        WHERE step_key IN ('recommendations', 'diagnostics', 'runbooks')
        """
    )


def downgrade() -> None:
    """Restore the legacy key name for the diagnosis stage.

    Rows removed for the old diagnostics and runbooks stages are not restored.
    """
    op.execute(
        """
        UPDATE llm_step_configs
        SET step_key = 'recommendations'
        WHERE step_key = 'diagnose'
        """
    )
