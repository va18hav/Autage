"""rename the evidence collection LLM step to investigate

Revision ID: f2a7c9d4e6b1
Revises: c7e2f9a1b3d4
Create Date: 2026-11-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f2a7c9d4e6b1'
down_revision: Union[str, Sequence[str], None] = 'c7e2f9a1b3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keep existing model routing when the pipeline step is renamed."""
    op.execute(
        """
        UPDATE llm_step_configs AS target
        SET step_key = 'investigate'
        WHERE target.step_key = 'collect_evidence'
          AND NOT EXISTS (
              SELECT 1
              FROM llm_step_configs AS existing
              WHERE existing.step_key = 'investigate'
          )
        """
    )
    op.execute(
        """
        DELETE FROM llm_step_configs
        WHERE step_key = 'collect_evidence'
        """
    )


def downgrade() -> None:
    """Restore the legacy step key."""
    op.execute(
        """
        UPDATE llm_step_configs AS target
        SET step_key = 'collect_evidence'
        WHERE target.step_key = 'investigate'
          AND NOT EXISTS (
              SELECT 1
              FROM llm_step_configs AS existing
              WHERE existing.step_key = 'collect_evidence'
          )
        """
    )
    op.execute(
        """
        DELETE FROM llm_step_configs
        WHERE step_key = 'investigate'
        """
    )
