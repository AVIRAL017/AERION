"""create_international_boundaries_table

Revision ID: 7a8b9c0d1e2f
Revises: 58e2a3c4d5f6
Create Date: 2026-09-10 11:27:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, Sequence[str], None] = '58e2a3c4d5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create international_boundaries table
    op.create_table(
        'international_boundaries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('geospatial_datasets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_record_id', sa.String(length=100), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('boundary_type', sa.String(length=100), server_default='INTERNATIONAL_OPERATIONAL', nullable=False),
        sa.Column('geom_4326', geoalchemy2.Geometry(geometry_type='GEOMETRY', srid=4326, spatial_index=True), nullable=False),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_international_boundaries_dataset_id', 'international_boundaries', ['dataset_id'])
    op.create_index('ix_international_boundaries_source_record_id', 'international_boundaries', ['source_record_id'])
    op.create_index('ix_international_boundaries_name', 'international_boundaries', ['name'])
    op.create_index('ix_international_boundaries_boundary_type', 'international_boundaries', ['boundary_type'])
    op.create_index('ix_intl_boundaries_type_name', 'international_boundaries', ['boundary_type', 'name'])


def downgrade() -> None:
    op.drop_index('ix_intl_boundaries_type_name', table_name='international_boundaries')
    op.drop_index('ix_international_boundaries_boundary_type', table_name='international_boundaries')
    op.drop_index('ix_international_boundaries_name', table_name='international_boundaries')
    op.drop_index('ix_international_boundaries_source_record_id', table_name='international_boundaries')
    op.drop_index('ix_international_boundaries_dataset_id', table_name='international_boundaries')
    op.drop_table('international_boundaries')
