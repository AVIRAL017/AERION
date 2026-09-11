"""add_google_auth_fields_to_users

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-12 01:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add auth_provider column (defaults to 'local')
    op.add_column(
        'users',
        sa.Column('auth_provider', sa.String(length=50), nullable=False, server_default='local')
    )
    # 2. Add provider_sub column (unique, indexed for fast O(1) external subject lookup)
    op.add_column(
        'users',
        sa.Column('provider_sub', sa.String(length=255), nullable=True)
    )
    op.create_index('ix_users_provider_sub', 'users', ['provider_sub'], unique=True)

    # 3. Add display_name column
    op.add_column(
        'users',
        sa.Column('display_name', sa.String(length=255), nullable=True)
    )

    # 4. Make hashed_password nullable for OAuth-only accounts
    op.alter_column('users', 'hashed_password', existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    op.alter_column('users', 'hashed_password', existing_type=sa.String(length=255), nullable=False)
    op.drop_column('users', 'display_name')
    op.drop_index('ix_users_provider_sub', table_name='users')
    op.drop_column('users', 'provider_sub')
    op.drop_column('users', 'auth_provider')
