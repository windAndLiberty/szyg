"""add usage pricing snapshot

Revision ID: d41c7f2057a1
Revises: c67d915ea204
"""

from alembic import op
import sqlalchemy as sa


revision = "d41c7f2057a1"
down_revision = "c67d915ea204"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usage_events", sa.Column("provider_model", sa.String(length=180), nullable=False, server_default=""))
    op.add_column("usage_events", sa.Column("pricing_snapshot", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("usage_events", "pricing_snapshot")
    op.drop_column("usage_events", "provider_model")
