"""Enforce one SIMPLE record set per zone/name/type without rebuilding SQLite.

Revision ID: 0002_record_set_uniqueness
Revises: 0001_core_tables
"""

from alembic import op

revision = "0002_record_set_uniqueness"
down_revision = "0001_core_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A unique index enforces the same key as UNIQUE, without a table-copy migration.
    # Existing duplicates cause migration failure; historical data is never deleted.
    op.create_index("uq_dns_records_zone_name_type", "dns_records",
                    ["hosted_zone_id", "name", "record_type"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_dns_records_zone_name_type", table_name="dns_records")
