"""add_hazard_seismic_fields

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
Create Date: 2026-09-10 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c0d1e2f3a4b'
down_revision: Union[str, None] = '8b9c0d1e2f3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'historical_hazard_records',
        sa.Column('magnitude', sa.Numeric(precision=4, scale=2), nullable=True)
    )
    op.add_column(
        'historical_hazard_records',
        sa.Column('depth_km', sa.Float(), nullable=True)
    )
    op.add_column(
        'historical_hazard_records',
        sa.Column('event_time', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        'ix_hist_hazard_magnitude',
        'historical_hazard_records',
        ['magnitude']
    )


def downgrade() -> None:
    op.drop_index('ix_hist_hazard_magnitude', table_name='historical_hazard_records')
    op.drop_column('historical_hazard_records', 'event_time')
    op.drop_column('historical_hazard_records', 'depth_km')
    op.drop_column('historical_hazard_records', 'magnitude')
