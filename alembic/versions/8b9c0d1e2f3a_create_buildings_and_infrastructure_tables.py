"""create_buildings_and_infrastructure_tables

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-09-10 12:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = '8b9c0d1e2f3a'
down_revision: Union[str, None] = '7a8b9c0d1e2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create building_footprints table
    op.create_table(
        'building_footprints',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('geospatial_datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_record_id', sa.String(length=100), nullable=True),
        sa.Column('building_type', sa.String(length=100), nullable=False, server_default='GENERAL'),
        sa.Column('damage_status', sa.String(length=50), nullable=False, server_default='NOT_ASSESSED'),
        sa.Column('area_m2', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('area_provenance', sa.String(length=50), nullable=False, server_default='DERIVED'),
        sa.Column('height', sa.Float(), nullable=True),
        sa.Column('levels', sa.Integer(), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column(
            'geom_4326',
            geoalchemy2.Geometry(geometry_type='GEOMETRY', srid=4326, spatial_index=True),
            nullable=False
        ),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_building_footprints_dataset_id', 'building_footprints', ['dataset_id'])
    op.create_index('ix_building_footprints_source_record_id', 'building_footprints', ['source_record_id'])
    op.create_index('ix_building_footprints_building_type', 'building_footprints', ['building_type'])
    op.create_index('ix_building_footprints_damage_status', 'building_footprints', ['damage_status'])

    # 2. Create critical_infrastructure table
    op.create_table(
        'critical_infrastructure',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('geospatial_datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_record_id', sa.String(length=100), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('infrastructure_type', sa.String(length=100), nullable=False),
        sa.Column('subtype', sa.String(length=100), nullable=True),
        sa.Column('operational_status', sa.String(length=50), nullable=False, server_default='UNKNOWN'),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('state_code', sa.String(length=50), nullable=True),
        sa.Column('district_code', sa.String(length=50), nullable=True),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column(
            'geom_4326',
            geoalchemy2.Geometry(geometry_type='GEOMETRY', srid=4326, spatial_index=True),
            nullable=False
        ),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_critical_infra_dataset_id', 'critical_infrastructure', ['dataset_id'])
    op.create_index('ix_critical_infra_source_record_id', 'critical_infrastructure', ['source_record_id'])
    op.create_index('ix_critical_infra_name', 'critical_infrastructure', ['name'])
    op.create_index('ix_critical_infra_type', 'critical_infrastructure', ['infrastructure_type'])
    op.create_index('ix_critical_infra_operational_status', 'critical_infrastructure', ['operational_status'])
    op.create_index('ix_critical_infra_state_district', 'critical_infrastructure', ['state_code', 'district_code'])


def downgrade() -> None:
    op.drop_index('ix_critical_infra_state_district', table_name='critical_infrastructure')
    op.drop_index('ix_critical_infra_operational_status', table_name='critical_infrastructure')
    op.drop_index('ix_critical_infra_type', table_name='critical_infrastructure')
    op.drop_index('ix_critical_infra_name', table_name='critical_infrastructure')
    op.drop_index('ix_critical_infra_source_record_id', table_name='critical_infrastructure')
    op.drop_index('ix_critical_infra_dataset_id', table_name='critical_infrastructure')
    op.drop_table('critical_infrastructure')

    op.drop_index('ix_building_footprints_damage_status', table_name='building_footprints')
    op.drop_index('ix_building_footprints_building_type', table_name='building_footprints')
    op.drop_index('ix_building_footprints_source_record_id', table_name='building_footprints')
    op.drop_index('ix_building_footprints_dataset_id', table_name='building_footprints')
    op.drop_table('building_footprints')
