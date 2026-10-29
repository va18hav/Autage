"""enforce single user account

Revision ID: a3f8c1d2e4b6
Revises: b7c9e1f2a3d4
Create Date: 2026-10-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f8c1d2e4b6'
down_revision: Union[str, Sequence[str], None] = 'b7c9e1f2a3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Guarantee that the users table can contain at most one row."""
    op.add_column(
        'users',
        sa.Column(
            'instance_key',
            sa.SmallInteger(),
            server_default=sa.text('1'),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        'ck_users_single_instance_key',
        'users',
        'instance_key = 1',
    )
    op.create_unique_constraint(
        'uq_users_single_instance',
        'users',
        ['instance_key'],
    )


def downgrade() -> None:
    """Remove the single-user database invariant."""
    op.drop_constraint('uq_users_single_instance', 'users', type_='unique')
    op.drop_constraint(
        'ck_users_single_instance_key',
        'users',
        type_='check',
    )
    op.drop_column('users', 'instance_key')
