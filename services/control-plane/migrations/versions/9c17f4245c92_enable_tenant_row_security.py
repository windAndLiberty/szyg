"""enable tenant row security

Revision ID: 9c17f4245c92
Revises: e345e0bdd3f0
"""
from typing import Sequence, Union

from alembic import op

revision: str = "9c17f4245c92"
down_revision: Union[str, None] = "e345e0bdd3f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in ("usage_events", "feedback"):
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(
            f"CREATE POLICY {table}_tenant_policy ON {table} "
            "USING (organization_id = nullif(current_setting('app.organization_id', true), '')) "
            "WITH CHECK (organization_id = nullif(current_setting('app.organization_id', true), ''))"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in ("usage_events", "feedback"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_policy ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
