"""extend_shelters_schema

Revision ID: 58e2a3c4d5f6
Revises: 49b71f92e401
Create Date: 2026-09-10 10:46:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '58e2a3c4d5f6'
down_revision: Union[str, Sequence[str], None] = '49b71f92e401'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Make project_id nullable so reference/global shelters can exist
    op.alter_column('shelters', 'project_id', existing_type=postgresql.UUID(as_uuid=True), nullable=True)

    # 2. Add new columns
    op.add_column('shelters', sa.Column('dataset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('geospatial_datasets.id', ondelete='SET NULL'), nullable=True))
    op.add_column('shelters', sa.Column('source_record_id', sa.String(length=100), nullable=True))
    op.add_column('shelters', sa.Column('shelter_type', sa.String(length=100), server_default='UNKNOWN', nullable=False))
    op.add_column('shelters', sa.Column('operational_status', sa.String(length=50), server_default='UNKNOWN', nullable=False))
    
    # Capacity columns: make capacity_total and capacity_occupied nullable
    op.alter_column('shelters', 'capacity_total', existing_type=sa.Integer(), nullable=True)
    op.alter_column('shelters', 'capacity_occupied', existing_type=sa.Integer(), nullable=True)
    op.add_column('shelters', sa.Column('capacity_status', sa.String(length=50), server_default='NOT_PROVIDED', nullable=False))

    # Services & Facilities
    op.add_column('shelters', sa.Column('accessibility', sa.Text(), nullable=True))
    op.add_column('shelters', sa.Column('contact_information', sa.Text(), nullable=True))
    op.add_column('shelters', sa.Column('opening_hours', sa.String(length=255), nullable=True))
    op.add_column('shelters', sa.Column('services', postgresql.ARRAY(sa.String()), server_default='{}', nullable=False))
    op.add_column('shelters', sa.Column('address', sa.Text(), nullable=True))

    # Administrative enrichment
    op.add_column('shelters', sa.Column('state_code', sa.String(length=50), nullable=True))
    op.add_column('shelters', sa.Column('district_code', sa.String(length=50), nullable=True))

    # Metadata & timestamps
    op.add_column('shelters', sa.Column('source_url', sa.String(length=1024), nullable=True))
    op.add_column('shelters', sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False))
    op.add_column('shelters', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False))
    op.add_column('shelters', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False))

    # 3. Create indexes
    op.create_index('ix_shelters_dataset_id', 'shelters', ['dataset_id'])
    op.create_index('ix_shelters_source_record_id', 'shelters', ['source_record_id'])
    op.create_index('ix_shelters_name', 'shelters', ['name'])
    op.create_index('ix_shelters_shelter_type', 'shelters', ['shelter_type'])
    op.create_index('ix_shelters_operational_status', 'shelters', ['operational_status'])
    op.create_index('ix_shelters_state_code', 'shelters', ['state_code'])
    op.create_index('ix_shelters_district_code', 'shelters', ['district_code'])
    op.create_index('ix_shelters_state_district', 'shelters', ['state_code', 'district_code'])
    op.create_index('ix_shelters_op_status', 'shelters', ['operational_status'])
    op.create_index('ix_shelters_type', 'shelters', ['shelter_type'])


def downgrade() -> None:
    op.drop_index('ix_shelters_type', table_name='shelters')
    op.drop_index('ix_shelters_op_status', table_name='shelters')
    op.drop_index('ix_shelters_state_district', table_name='shelters')
    op.drop_index('ix_shelters_district_code', table_name='shelters')
    op.drop_index('ix_shelters_state_code', table_name='shelters')
    op.drop_index('ix_shelters_operational_status', table_name='shelters')
    op.drop_index('ix_shelters_shelter_type', table_name='shelters')
    op.drop_index('ix_shelters_name', table_name='shelters')
    op.drop_index('ix_shelters_source_record_id', table_name='shelters')
    op.drop_index('ix_shelters_dataset_id', table_name='shelters')

    op.drop_column('shelters', 'updated_at')
    op.drop_column('shelters', 'created_at')
    op.drop_column('shelters', 'metadata_json')
    op.drop_column('shelters', 'source_url')
    op.drop_column('shelters', 'district_code')
    op.drop_column('shelters', 'state_code')
    op.drop_column('shelters', 'address')
    op.drop_column('shelters', 'services')
    op.drop_column('shelters', 'opening_hours')
    op.drop_column('shelters', 'contact_information')
    op.drop_column('shelters', 'accessibility')
    op.drop_column('shelters', 'capacity_status')
    op.alter_column('shelters', 'capacity_occupied', existing_type=sa.Integer(), nullable=False)
    op.alter_column('shelters', 'capacity_total', existing_type=sa.Integer(), nullable=False)
    op.drop_column('shelters', 'operational_status')
    op.drop_column('shelters', 'shelter_type')
    op.drop_column('shelters', 'source_record_id')
    op.drop_column('shelters', 'dataset_id')
    op.alter_column('shelters', 'project_id', existing_type=postgresql.UUID(as_uuid=True), nullable=False)
