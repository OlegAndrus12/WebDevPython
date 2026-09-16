"""add users.role

Revision ID: 31dd488df6fe
Revises: af4fea44120e
Create Date: 2026-09-10 12:40:18.951163

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '31dd488df6fe'
down_revision: Union[str, Sequence[str], None] = 'af4fea44120e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Hand-written: add_column does not create the enum type, so it is created here
    # first and create_type=False stops add_column trying again.
    role = postgresql.ENUM("user", "admin", name="user_role", create_type=False)
    role.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "users",
        sa.Column("role", role, server_default="user", nullable=False),
    )

    # No backfill: server_default makes every existing row a 'user', and admin is
    # granted by hand afterwards (UPDATE users SET role = 'admin' WHERE email = '...').


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "role")

    # Required: dropping the column leaves the type behind, and the next upgrade
    # would then fail with "type user_role already exists".
    postgresql.ENUM(name="user_role").drop(op.get_bind(), checkfirst=True)
