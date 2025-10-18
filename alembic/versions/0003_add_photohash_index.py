"""add photo_hash index

Revision ID: 0003_add_photohash_index
Revises: 0002_add_md5_index
Create Date: 2025-10-18 00:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003_add_photohash_index'
down_revision = '0002_add_md5_index'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # create an index on photo_hash to speed visual-hash lookups
    op.create_index('ix_files_photo_hash', 'files', ['photo_hash'])


def downgrade() -> None:
    op.drop_index('ix_files_photo_hash', table_name='files')
