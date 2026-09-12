"""add multi-product wallets and immutable credit ledger

Revision ID: a91e6f0c2b74
Revises: d41c7f2057a1
"""

from alembic import op
import sqlalchemy as sa


revision = "a91e6f0c2b74"
down_revision = "d41c7f2057a1"
branch_labels = None
depends_on = None

PRIVATE = "szyg_private"


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.String(length=48), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("registration_mode", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_products_status", "products", ["status"])
    op.execute(sa.text(
        "INSERT INTO products (id, name, registration_mode, status, created_at) VALUES "
        "(:private_id, :private_name, 'invite_only', 'active', CURRENT_TIMESTAMP), "
        "(:public_id, :public_name, 'self_service', 'active', CURRENT_TIMESTAMP)"
    ).bindparams(
        private_id=PRIVATE,
        private_name="数字员工",
        public_id="xiaoyu_public",
        public_name="小妤数字员工",
    ))

    for table in ("organizations", "users", "invitations", "usage_events", "credit_transactions"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("product_id", sa.String(length=48), nullable=False, server_default=PRIVATE))
            batch.create_foreign_key(f"fk_{table}_product_id", "products", ["product_id"], ["id"])
            batch.create_index(f"ix_{table}_product_id", ["product_id"])

    with op.batch_alter_table("login_device_blocks") as batch:
        batch.add_column(sa.Column("product_id", sa.String(length=48), nullable=False, server_default=PRIVATE))
        batch.create_foreign_key("fk_login_device_blocks_product_id", "products", ["product_id"], ["id"])
        batch.create_index("ix_login_device_blocks_product_id", ["product_id"])
    op.drop_index("ix_login_device_blocks_identity_key", table_name="login_device_blocks")
    op.create_index("ix_login_device_blocks_identity_key", "login_device_blocks", ["identity_key"], unique=False)
    with op.batch_alter_table("login_device_blocks") as batch:
        batch.create_unique_constraint("uq_login_block_product_identity", ["product_id", "identity_key"])

    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    with op.batch_alter_table("users") as batch:
        batch.create_unique_constraint("uq_users_product_email", ["product_id", "email"])

    op.create_table(
        "credit_wallets",
        sa.Column("id", sa.String(length=48), primary_key=True),
        sa.Column("product_id", sa.String(length=48), nullable=False),
        sa.Column("organization_id", sa.String(length=48), nullable=False),
        sa.Column("user_id", sa.String(length=48), nullable=False),
        sa.Column("balance_micros", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("reserved_micros", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("product_id", "user_id", name="uq_credit_wallet_product_user"),
    )
    for column in ("product_id", "organization_id", "user_id", "status"):
        op.create_index(f"ix_credit_wallets_{column}", "credit_wallets", [column])

    with op.batch_alter_table("usage_events") as batch:
        batch.add_column(sa.Column("wallet_id", sa.String(length=48), nullable=True))
        batch.add_column(sa.Column("reserved_credits_micros", sa.BigInteger(), nullable=False, server_default="0"))
        batch.create_foreign_key("fk_usage_events_wallet_id", "credit_wallets", ["wallet_id"], ["id"])
        batch.create_index("ix_usage_events_wallet_id", ["wallet_id"])
    with op.batch_alter_table("credit_transactions") as batch:
        batch.add_column(sa.Column("wallet_id", sa.String(length=48), nullable=True))
        batch.create_foreign_key("fk_credit_transactions_wallet_id", "credit_wallets", ["wallet_id"], ["id"])
        batch.create_index("ix_credit_transactions_wallet_id", ["wallet_id"])

    op.create_table(
        "credit_ledger_entries",
        sa.Column("id", sa.String(length=48), primary_key=True),
        sa.Column("product_id", sa.String(length=48), nullable=False),
        sa.Column("organization_id", sa.String(length=48), nullable=False),
        sa.Column("user_id", sa.String(length=48), nullable=False),
        sa.Column("wallet_id", sa.String(length=48), nullable=False),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("credits_delta_micros", sa.BigInteger(), nullable=False),
        sa.Column("balance_after_micros", sa.BigInteger(), nullable=False),
        sa.Column("payment_amount_micros", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="CNY"),
        sa.Column("payment_order_id", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("reference_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("usage_event_id", sa.String(length=48), nullable=True),
        sa.Column("operator_user_id", sa.String(length=48), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("note", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["wallet_id"], ["credit_wallets.id"]),
        sa.ForeignKeyConstraint(["usage_event_id"], ["usage_events.id"]),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"]),
        sa.UniqueConstraint("wallet_id", "idempotency_key", name="uq_credit_ledger_wallet_idempotency"),
    )
    for column in (
        "product_id", "organization_id", "user_id", "wallet_id", "entry_type",
        "payment_order_id", "reference_id", "usage_event_id", "operator_user_id", "created_at",
    ):
        op.create_index(f"ix_credit_ledger_entries_{column}", "credit_ledger_entries", [column])

    if op.get_bind().dialect.name == "postgresql":
        for table in ("credit_wallets", "credit_ledger_entries"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY {table}_tenant_policy ON {table} "
                "USING (organization_id = nullif(current_setting('app.organization_id', true), '')) "
                "WITH CHECK (organization_id = nullif(current_setting('app.organization_id', true), ''))"
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in ("credit_ledger_entries", "credit_wallets"):
            op.execute(f"DROP POLICY IF EXISTS {table}_tenant_policy ON {table}")
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_table("credit_ledger_entries")
    with op.batch_alter_table("credit_transactions") as batch:
        batch.drop_index("ix_credit_transactions_wallet_id")
        batch.drop_constraint("fk_credit_transactions_wallet_id", type_="foreignkey")
        batch.drop_column("wallet_id")
    with op.batch_alter_table("usage_events") as batch:
        batch.drop_index("ix_usage_events_wallet_id")
        batch.drop_constraint("fk_usage_events_wallet_id", type_="foreignkey")
        batch.drop_column("reserved_credits_micros")
        batch.drop_column("wallet_id")
    op.drop_table("credit_wallets")
    with op.batch_alter_table("login_device_blocks") as batch:
        batch.drop_constraint("uq_login_block_product_identity", type_="unique")
    op.drop_index("ix_login_device_blocks_identity_key", table_name="login_device_blocks")
    op.create_index("ix_login_device_blocks_identity_key", "login_device_blocks", ["identity_key"], unique=True)
    with op.batch_alter_table("login_device_blocks") as batch:
        batch.drop_index("ix_login_device_blocks_product_id")
        batch.drop_constraint("fk_login_device_blocks_product_id", type_="foreignkey")
        batch.drop_column("product_id")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_product_email", type_="unique")
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    for table in reversed(("organizations", "users", "invitations", "usage_events", "credit_transactions")):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_product_id")
            batch.drop_constraint(f"fk_{table}_product_id", type_="foreignkey")
            batch.drop_column("product_id")
    op.drop_index("ix_products_status", table_name="products")
    op.drop_table("products")
