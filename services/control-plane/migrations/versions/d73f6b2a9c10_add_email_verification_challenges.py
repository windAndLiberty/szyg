"""add email verification challenges

Revision ID: d73f6b2a9c10
Revises: b27f840a6c19
"""

from alembic import op
import sqlalchemy as sa


revision = "d73f6b2a9c10"
down_revision = "b27f840a6c19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_verification_challenges",
        sa.Column("id", sa.String(length=48), primary_key=True),
        sa.Column("product_id", sa.String(length=48), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False, server_default="register"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ip_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("device_fingerprint_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("installation_id_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
    )
    for column in (
        "product_id", "email", "purpose", "status", "ip_hash",
        "device_fingerprint_hash", "installation_id_hash", "expires_at", "created_at",
    ):
        op.create_index(
            f"ix_email_verification_challenges_{column}",
            "email_verification_challenges",
            [column],
        )


def downgrade() -> None:
    op.drop_table("email_verification_challenges")
