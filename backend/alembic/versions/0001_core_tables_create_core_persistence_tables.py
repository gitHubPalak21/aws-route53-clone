"""Create core persistence tables

Revision ID: 0001_core_tables
Revises: none
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0001_core_tables'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Parents precede children so foreign keys are valid on every dialect.
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('display_name', sa.String(length=128), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(create_constraint=True, name='is_active_boolean'), server_default=sa.text('1'), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    op.create_table('hosted_zones',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=253), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('zone_type', sa.Enum('PUBLIC', 'PRIVATE', name='zone_type', native_enum=False, create_constraint=True), server_default='PUBLIC', nullable=False),
    sa.Column('vpc_id', sa.String(length=32), nullable=True),
    sa.Column('region', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint("zone_type != 'PRIVATE' OR (vpc_id IS NOT NULL AND length(trim(vpc_id)) > 0 AND region IS NOT NULL AND length(trim(region)) > 0)", name=op.f('ck_hosted_zones_private_zone_vpc')),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_hosted_zones_owner_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_hosted_zones'))
    )
    with op.batch_alter_table('hosted_zones', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_hosted_zones_name'), ['name'], unique=False)
        batch_op.create_index(batch_op.f('ix_hosted_zones_owner_id'), ['owner_id'], unique=False)

    op.create_table('sessions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=255), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sessions'))
    )
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sessions_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_sessions_token_hash'), ['token_hash'], unique=True)
        batch_op.create_index(batch_op.f('ix_sessions_user_id'), ['user_id'], unique=False)

    op.create_table('dns_records',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('hosted_zone_id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=253), nullable=False),
    sa.Column('record_type', sa.Enum('A', 'AAAA', 'CNAME', 'TXT', 'MX', 'NS', 'PTR', 'SRV', 'CAA', 'SOA', name='record_type', native_enum=False, create_constraint=True), nullable=False),
    sa.Column('values', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    sa.Column('ttl', sa.Integer(), server_default=sa.text('(300)'), nullable=True),
    sa.Column('routing_policy', sa.Enum('SIMPLE', name='routing_policy', native_enum=False, create_constraint=True), server_default='SIMPLE', nullable=False),
    sa.Column('alias', sa.Boolean(create_constraint=True, name='alias_boolean'), server_default=sa.text('0'), nullable=False),
    sa.Column('alias_target', sa.JSON(none_as_null=True), nullable=True),
    sa.Column('is_system', sa.Boolean(create_constraint=True, name='is_system_boolean'), server_default=sa.text('0'), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint('json_type("values") = \'array\'', name=op.f('ck_dns_records_values_array')),
    sa.CheckConstraint('ttl IS NULL OR ttl > 0', name=op.f('ck_dns_records_positive_ttl')),
    sa.ForeignKeyConstraint(['hosted_zone_id'], ['hosted_zones.id'], name=op.f('fk_dns_records_hosted_zone_id_hosted_zones'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_dns_records'))
    )
    with op.batch_alter_table('dns_records', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_dns_records_hosted_zone_id'), ['hosted_zone_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_dns_records_name'), ['name'], unique=False)
        batch_op.create_index(batch_op.f('ix_dns_records_record_type'), ['record_type'], unique=False)



def downgrade() -> None:
    # Drop children before parents; this removes application data as well.
    with op.batch_alter_table('dns_records', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_dns_records_record_type'))
        batch_op.drop_index(batch_op.f('ix_dns_records_name'))
        batch_op.drop_index(batch_op.f('ix_dns_records_hosted_zone_id'))

    op.drop_table('dns_records')
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sessions_user_id'))
        batch_op.drop_index(batch_op.f('ix_sessions_token_hash'))
        batch_op.drop_index(batch_op.f('ix_sessions_expires_at'))

    op.drop_table('sessions')
    with op.batch_alter_table('hosted_zones', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_hosted_zones_owner_id'))
        batch_op.drop_index(batch_op.f('ix_hosted_zones_name'))

    op.drop_table('hosted_zones')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))

    op.drop_table('users')
