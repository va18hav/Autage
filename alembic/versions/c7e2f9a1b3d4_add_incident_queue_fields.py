"""add incident queue fields

Revision ID: c7e2f9a1b3d4
Revises: a3f8c1d2e4b6
Create Date: 2026-10-30 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e2f9a1b3d4'
down_revision: Union[str, Sequence[str], None] = 'a3f8c1d2e4b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add queue and retry fields used by the Postgres-backed worker loop."""
    op.add_column(
        'incidents',
        sa.Column(
            'attempts',
            sa.Integer(),
            server_default=sa.text('0'),
            nullable=False,
        ),
    )
    op.add_column(
        'incidents',
        sa.Column(
            'next_attempt_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )
    op.add_column(
        'incidents',
        sa.Column(
            'locked_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        'incidents',
        sa.Column('last_error', sa.Text(), nullable=True),
    )
    op.create_index(
        'ix_incidents_pending_queue',
        'incidents',
        ['next_attempt_at', 'created_at'],
        unique=False,
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_index(
        'ix_incidents_triaging_queue',
        'incidents',
        ['locked_at', 'created_at'],
        unique=False,
        postgresql_where=sa.text("status = 'TRIAGING'"),
    )


def downgrade() -> None:
    """Remove the queue and retry fields."""
    op.drop_index(
        'ix_incidents_triaging_queue',
        table_name='incidents',
        postgresql_where=sa.text("status = 'TRIAGING'"),
    )
    op.drop_index(
        'ix_incidents_pending_queue',
        table_name='incidents',
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.drop_column('incidents', 'last_error')
    op.drop_column('incidents', 'locked_at')
    op.drop_column('incidents', 'next_attempt_at')
    op.drop_column('incidents', 'attempts')
