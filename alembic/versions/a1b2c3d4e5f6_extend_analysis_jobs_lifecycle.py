"""extend_analysis_jobs_lifecycle

Revision ID: a1b2c3d4e5f6
Revises: 9c0d1e2f3a4b
Create Date: 2026-09-10 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '9c0d1e2f3a4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'analysis_jobs',
        sa.Column('current_stage', sa.String(length=100), nullable=True, server_default='SUBMITTED')
    )
    op.add_column(
        'analysis_jobs',
        sa.Column('idempotency_key', sa.String(length=255), nullable=True)
    )
    op.add_column(
        'analysis_jobs',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column(
        'analysis_jobs',
        sa.Column('input_asset_reference', sa.String(length=1024), nullable=True)
    )
    op.add_column(
        'analysis_jobs',
        sa.Column('limitations', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.create_index(
        'ix_analysis_jobs_idempotency_key',
        'analysis_jobs',
        ['project_id', 'idempotency_key']
    )


def downgrade() -> None:
    op.drop_index('ix_analysis_jobs_idempotency_key', table_name='analysis_jobs')
    op.drop_column('analysis_jobs', 'limitations')
    op.drop_column('analysis_jobs', 'input_asset_reference')
    op.drop_column('analysis_jobs', 'user_id')
    op.drop_column('analysis_jobs', 'idempotency_key')
    op.drop_column('analysis_jobs', 'current_stage')
