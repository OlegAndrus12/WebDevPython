"""add users.subscribed

Revision ID: af4fea44120e
Revises: c0bc5faeef11
Create Date: 2026-09-10 11:06:55.938325

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af4fea44120e'
down_revision: Union[str, Sequence[str], None] = 'c0bc5faeef11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('subscribed', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    # No backfill on purpose: subscribing is an opt-in, so false is right for
    # existing readers (unlike `confirmed` in c0bc5faeef11, which needed one).


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'subscribed')
