"""add md5 index

Revision ID: 0002_add_md5_index
Revises: 0001_initial
Create Date: 2025-10-18 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_add_md5_index'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # create an index on md5_hash to speed duplicate lookup
    op.create_index('ix_files_md5_hash', 'files', ['md5_hash'])


def downgrade() -> None:
    op.drop_index('ix_files_md5_hash', table_name='files')
