"""add credit transactions

Revision ID: f021a9d7c430
Revises: b6b0b15578ca
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f021a9d7c430"
down_revision: Union[str, None] = "b6b0b15578ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.String(length=48), nullable=False),
        sa.Column("organization_id", sa.String(length=48), nullable=False),
        sa.Column("user_id", sa.String(length=48), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("credits_micros", sa.BigInteger(), nullable=False),
        sa.Column("payment_amount_micros", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("note", sa.String(length=240), nullable=False),
        sa.Column("reference_id", sa.String(length=120), nullable=False),
        sa.Column("created_by", sa.String(length=48), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_credit_transactions_created_at"), "credit_transactions", ["created_at"], unique=False)
    op.create_index(op.f("ix_credit_transactions_created_by"), "credit_transactions", ["created_by"], unique=False)
    op.create_index(op.f("ix_credit_transactions_kind"), "credit_transactions", ["kind"], unique=False)
    op.create_index(op.f("ix_credit_transactions_organization_id"), "credit_transactions", ["organization_id"], unique=False)
    op.create_index(op.f("ix_credit_transactions_reference_id"), "credit_transactions", ["reference_id"], unique=False)
    op.create_index(op.f("ix_credit_transactions_user_id"), "credit_transactions", ["user_id"], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE credit_transactions ENABLE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY credit_transactions_tenant_policy ON credit_transactions "
            "USING (organization_id = nullif(current_setting('app.organization_id', true), '')) "
            "WITH CHECK (organization_id = nullif(current_setting('app.organization_id', true), ''))"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS credit_transactions_tenant_policy ON credit_transactions")
        op.execute("ALTER TABLE credit_transactions DISABLE ROW LEVEL SECURITY")
    op.drop_index(op.f("ix_credit_transactions_user_id"), table_name="credit_transactions")
    op.drop_index(op.f("ix_credit_transactions_reference_id"), table_name="credit_transactions")
    op.drop_index(op.f("ix_credit_transactions_organization_id"), table_name="credit_transactions")
    op.drop_index(op.f("ix_credit_transactions_kind"), table_name="credit_transactions")
    op.drop_index(op.f("ix_credit_transactions_created_by"), table_name="credit_transactions")
    op.drop_index(op.f("ix_credit_transactions_created_at"), table_name="credit_transactions")
    op.drop_table("credit_transactions")
