"""add incident type and structured analysis

Revision ID: f4a1c2d3e5b6
Revises: c491a70d8e12
Create Date: 2026-10-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f4a1c2d3e5b6'
down_revision: Union[str, Sequence[str], None] = 'c491a70d8e12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'incidents',
        sa.Column('incident_type', sa.String(length=32), nullable=True),
    )
    op.add_column(
        'incidents',
        sa.Column(
            'analysis',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index(
        op.f('ix_incidents_incident_type'),
        'incidents',
        ['incident_type'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_incidents_incident_type'),
        table_name='incidents',
    )
    op.drop_column('incidents', 'analysis')
    op.drop_column('incidents', 'incident_type')
