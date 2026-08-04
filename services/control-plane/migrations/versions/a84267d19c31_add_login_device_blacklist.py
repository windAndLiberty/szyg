"""add login device blacklist

Revision ID: a84267d19c31
Revises: f021a9d7c430
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a84267d19c31"
down_revision: Union[str, None] = "f021a9d7c430"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "login_device_blocks",
        sa.Column("id", sa.String(length=48), nullable=False),
        sa.Column("identity_key", sa.String(length=160), nullable=False),
        sa.Column("installation_id", sa.String(length=160), nullable=False),
        sa.Column("fingerprint_hash", sa.String(length=128), nullable=False),
        sa.Column("device_name", sa.String(length=160), nullable=False),
        sa.Column("app_version", sa.String(length=40), nullable=False),
        sa.Column("attempted_account", sa.String(length=320), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("first_failure_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_login_device_blocks_identity_key"), "login_device_blocks", ["identity_key"], unique=True)
    op.create_index(op.f("ix_login_device_blocks_installation_id"), "login_device_blocks", ["installation_id"], unique=False)
    op.create_index(op.f("ix_login_device_blocks_fingerprint_hash"), "login_device_blocks", ["fingerprint_hash"], unique=False)
    op.create_index(op.f("ix_login_device_blocks_status"), "login_device_blocks", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_login_device_blocks_status"), table_name="login_device_blocks")
    op.drop_index(op.f("ix_login_device_blocks_fingerprint_hash"), table_name="login_device_blocks")
    op.drop_index(op.f("ix_login_device_blocks_installation_id"), table_name="login_device_blocks")
    op.drop_index(op.f("ix_login_device_blocks_identity_key"), table_name="login_device_blocks")
    op.drop_table("login_device_blocks")
