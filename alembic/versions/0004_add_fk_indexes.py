"""add indexes for duplicate_of_id and related_id

Revision ID: 0004_add_fk_indexes
Revises: 0003_add_photohash_index
Create Date: 2025-10-18 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0004_add_fk_indexes'
down_revision = '0003_add_photohash_index'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('ix_files_duplicate_of_id', 'files', ['duplicate_of_id'])
    op.create_index('ix_files_related_id', 'files', ['related_id'])


def downgrade() -> None:
    op.drop_index('ix_files_related_id', table_name='files')
    op.drop_index('ix_files_duplicate_of_id', table_name='files')
