"""limit daily password changes

Revision ID: c67d915ea204
Revises: a84267d19c31
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c67d915ea204"
down_revision: Union[str, None] = "a84267d19c31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")
