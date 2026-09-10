"""create_geospatial_data_layer

Revision ID: 49b71f92e401
Revises: 30831dc76d4c
Create Date: 2026-09-10 10:07:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = '49b71f92e401'
down_revision: Union[str, Sequence[str], None] = '30831dc76d4c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. geospatial_datasets
    op.create_table(
        'geospatial_datasets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('dataset_id', sa.String(length=100), nullable=False),
        sa.Column('dataset_name', sa.String(length=255), nullable=False),
        sa.Column('source_name', sa.String(length=255), nullable=False),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('acquisition_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('license', sa.String(length=255), nullable=False),
        sa.Column('attribution', sa.Text(), nullable=False),
        sa.Column('geographic_scope', sa.String(length=100), nullable=False),
        sa.Column('geometry_type', sa.String(length=50), nullable=False),
        sa.Column('crs', sa.String(length=50), nullable=False),
        sa.Column('source_format', sa.String(length=50), nullable=False),
        sa.Column('checksum', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='ACTIVE', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_geospatial_datasets_dataset_id', 'geospatial_datasets', ['dataset_id'], unique=True)
    op.create_index('ix_geospatial_datasets_checksum', 'geospatial_datasets', ['checksum'])

    # 2. administrative_boundaries
    op.create_table(
        'administrative_boundaries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('geospatial_datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('level', sa.String(length=10), nullable=False),
        sa.Column('country_code', sa.String(length=10), server_default='IND', nullable=False),
        sa.Column('state_code', sa.String(length=50), nullable=True),
        sa.Column('district_code', sa.String(length=50), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('name_canonical', sa.String(length=255), nullable=False),
        sa.Column('source_id', sa.String(length=100), nullable=True),
        sa.Column('geom_4326', geoalchemy2.Geometry(geometry_type='MULTIPOLYGON', srid=4326, spatial_index=True), nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_administrative_boundaries_dataset_id', 'administrative_boundaries', ['dataset_id'])
    op.create_index('ix_administrative_boundaries_level', 'administrative_boundaries', ['level'])
    op.create_index('ix_administrative_boundaries_country_code', 'administrative_boundaries', ['country_code'])
    op.create_index('ix_administrative_boundaries_state_code', 'administrative_boundaries', ['state_code'])
    op.create_index('ix_administrative_boundaries_district_code', 'administrative_boundaries', ['district_code'])
    op.create_index('ix_administrative_boundaries_name', 'administrative_boundaries', ['name'])
    op.create_index('ix_administrative_boundaries_name_canonical', 'administrative_boundaries', ['name_canonical'])
    op.create_index('ix_admin_boundaries_level_state', 'administrative_boundaries', ['level', 'state_code'])
    op.create_index('ix_admin_boundaries_level_district', 'administrative_boundaries', ['level', 'district_code'])

    # 3. historical_hazard_records
    op.create_table(
        'historical_hazard_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('geospatial_datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('hazard_type', sa.String(length=100), server_default='HISTORICAL_FLOOD', nullable=False),
        sa.Column('source_event_id', sa.String(length=100), nullable=False),
        sa.Column('event_date_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('event_date_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('state_name', sa.String(length=255), nullable=True),
        sa.Column('district_name', sa.String(length=255), nullable=True),
        sa.Column('cause', sa.String(length=255), nullable=True),
        sa.Column('severity_reported', sa.String(length=100), nullable=True),
        sa.Column('impact_summary', sa.Text(), nullable=True),
        sa.Column('is_live_status', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('geom_4326', geoalchemy2.Geometry(geometry_type='GEOMETRY', srid=4326, spatial_index=True), nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_historical_hazard_records_dataset_id', 'historical_hazard_records', ['dataset_id'])
    op.create_index('ix_historical_hazard_records_hazard_type', 'historical_hazard_records', ['hazard_type'])
    op.create_index('ix_historical_hazard_records_source_event_id', 'historical_hazard_records', ['source_event_id'])
    op.create_index('ix_historical_hazard_records_state_name', 'historical_hazard_records', ['state_name'])
    op.create_index('ix_historical_hazard_records_district_name', 'historical_hazard_records', ['district_name'])
    op.create_index('ix_hist_hazard_type_event', 'historical_hazard_records', ['hazard_type', 'source_event_id'])


def downgrade() -> None:
    op.drop_table('historical_hazard_records')
    op.drop_table('administrative_boundaries')
    op.drop_table('geospatial_datasets')
