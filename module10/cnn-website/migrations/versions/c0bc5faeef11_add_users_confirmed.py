"""add users.confirmed

Revision ID: c0bc5faeef11
Revises: d37028d90694
Create Date: 2026-09-08 15:44:24.257639

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0bc5faeef11'
down_revision: Union[str, Sequence[str], None] = 'd37028d90694'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('confirmed', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    # Hand-added: server_default fills existing rows with false, which would lock
    # every account that predates verification out of login.
    op.execute("UPDATE users SET confirmed = true")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'confirmed')
