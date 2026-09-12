"""add alipay payment orders

Revision ID: b27f840a6c19
Revises: a91e6f0c2b74
"""

from alembic import op
import sqlalchemy as sa


revision = "b27f840a6c19"
down_revision = "a91e6f0c2b74"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_orders",
        sa.Column("id", sa.String(length=48), primary_key=True),
        sa.Column("product_id", sa.String(length=48), nullable=False),
        sa.Column("organization_id", sa.String(length=48), nullable=False),
        sa.Column("user_id", sa.String(length=48), nullable=False),
        sa.Column("wallet_id", sa.String(length=48), nullable=False),
        sa.Column("channel", sa.String(length=24), nullable=False, server_default="alipay"),
        sa.Column("merchant_order_no", sa.String(length=64), nullable=False),
        sa.Column("provider_trade_no", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("amount_micros", sa.BigInteger(), nullable=False),
        sa.Column("credits_micros", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="CNY"),
        sa.Column("subject", sa.String(length=120), nullable=False),
        sa.Column("notification", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["wallet_id"], ["credit_wallets.id"]),
        sa.UniqueConstraint("product_id", "merchant_order_no", name="uq_payment_product_merchant_order"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_payment_user_idempotency"),
    )
    for column in (
        "product_id", "organization_id", "user_id", "wallet_id", "channel",
        "merchant_order_no", "provider_trade_no", "status", "expires_at", "created_at",
    ):
        op.create_index(f"ix_payment_orders_{column}", "payment_orders", [column])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE payment_orders ENABLE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY payment_orders_tenant_policy ON payment_orders "
            "USING (organization_id = nullif(current_setting('app.organization_id', true), '')) "
            "WITH CHECK (organization_id = nullif(current_setting('app.organization_id', true), ''))"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS payment_orders_tenant_policy ON payment_orders")
        op.execute("ALTER TABLE payment_orders DISABLE ROW LEVEL SECURITY")
    op.drop_table("payment_orders")
