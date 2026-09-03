"""add real provider usage accounting

Revision ID: b6b0b15578ca
Revises: 9c17f4245c92
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b6b0b15578ca"
down_revision: Union[str, None] = "9c17f4245c92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("usage_events", sa.Column("provider_usage", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("usage_events", sa.Column("provider_cost_micros", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("usage_events", sa.Column("credits_charged_micros", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("usage_events", sa.Column("pricing_version", sa.String(length=40), nullable=False, server_default=""))
    op.create_table(
        "provider_billing_daily",
        sa.Column("id", sa.String(length=48), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("billing_date", sa.Date(), nullable=False),
        sa.Column("actual_cost_micros", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False),
        sa.Column("provider_request_id", sa.String(length=160), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "billing_date", name="uq_provider_billing_day"),
    )
    op.create_index(op.f("ix_provider_billing_daily_billing_date"), "provider_billing_daily", ["billing_date"], unique=False)
    op.create_index(op.f("ix_provider_billing_daily_provider"), "provider_billing_daily", ["provider"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_provider_billing_daily_provider"), table_name="provider_billing_daily")
    op.drop_index(op.f("ix_provider_billing_daily_billing_date"), table_name="provider_billing_daily")
    op.drop_table("provider_billing_daily")
    op.drop_column("usage_events", "pricing_version")
    op.drop_column("usage_events", "credits_charged_micros")
    op.drop_column("usage_events", "provider_cost_micros")
    op.drop_column("usage_events", "provider_usage")
