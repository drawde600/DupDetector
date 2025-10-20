"""Add application_locks table for process coordination

Revision ID: 0004_add_application_locks
Revises: 0003_add_timestamps_and_priority
Create Date: 2025-10-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_add_application_locks'
down_revision = '0003_add_timestamps_and_priority'
branch_labels = None
depends_on = None


def upgrade():
    """Add application_locks table."""

    op.create_table(
        'application_locks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('lock_name', sa.String(255), unique=True, nullable=False),
        sa.Column('process_id', sa.Integer(), nullable=False),
        sa.Column('hostname', sa.String(255), nullable=False),
        sa.Column('acquired_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True)
    )

    # Create index on lock_name for fast lookups
    op.create_index('ix_application_locks_lock_name', 'application_locks', ['lock_name'])


def downgrade():
    """Remove application_locks table."""

    op.drop_index('ix_application_locks_lock_name', 'application_locks')
    op.drop_table('application_locks')
