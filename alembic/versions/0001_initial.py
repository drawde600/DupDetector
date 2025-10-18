"""initial

Revision ID: 0001_initial
Revises: 
Create Date: 2025-10-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'files',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('path', sa.Text, nullable=False, unique=True),
        sa.Column('original_path', sa.Text, nullable=False),
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('original_name', sa.Text, nullable=False),
        sa.Column('size', sa.Integer, nullable=False),
        sa.Column('media_type', sa.Text, nullable=True),
        sa.Column('dimensions', sa.Text, nullable=True),
        sa.Column('manufacturer', sa.Text, nullable=True),
        sa.Column('gps', sa.Text, nullable=True),
        sa.Column('metadata', sa.Text, nullable=True),
        sa.Column('md5_hash', sa.Text, nullable=False),
        sa.Column('photo_hash', sa.Text, nullable=True),
        sa.Column('related_id', sa.Integer, nullable=True),
        sa.Column('is_duplicate', sa.Boolean, nullable=False, server_default=sa.text('0')),
        sa.Column('is_deleted', sa.Boolean, nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('duplicate_of_id', sa.Integer, nullable=True),
    )

    op.create_table(
        'tags',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.Text, nullable=False, unique=True),
    )

    op.create_table(
        'file_tags',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('file_id', sa.Integer, nullable=False),
        sa.Column('tag_id', sa.Integer, nullable=False),
    )


def downgrade() -> None:
    op.drop_table('file_tags')
    op.drop_table('tags')
    op.drop_table('files')
