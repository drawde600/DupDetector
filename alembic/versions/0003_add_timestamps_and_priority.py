"""Add timestamps to tags and file_tags, add priority to file_tags

Revision ID: 0003_add_timestamps_and_priority
Revises: 0002_add_tag_priority (or previous revision)
Create Date: 2025-10-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_add_timestamps_and_priority'
down_revision = None  # Update this to your previous revision
branch_labels = None
depends_on = None


def upgrade():
    """Add created_at, updated_at, and priority columns."""

    # Add timestamps to tags table
    op.add_column('tags',
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False)
    )
    op.add_column('tags',
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=False)
    )

    # Add priority and timestamps to file_tags table
    op.add_column('file_tags',
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0')
    )
    op.add_column('file_tags',
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False)
    )
    op.add_column('file_tags',
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), nullable=False)
    )

    # Assign priorities based on alphabetical order (maintain current behavior)
    # This ensures existing tags get sequential priorities per file
    op.execute("""
        UPDATE file_tags ft
        JOIN (
            SELECT
                ft2.id,
                ROW_NUMBER() OVER (PARTITION BY ft2.file_id ORDER BY t.name) - 1 as new_priority
            FROM file_tags ft2
            JOIN tags t ON ft2.tag_id = t.id
        ) ranked ON ft.id = ranked.id
        SET ft.priority = ranked.new_priority
    """)

    # Create composite index for efficient tag queries
    op.create_index('ix_file_tags_file_priority', 'file_tags', ['file_id', 'priority'])


def downgrade():
    """Remove added columns and index."""

    # Drop index
    op.drop_index('ix_file_tags_file_priority', 'file_tags')

    # Drop columns from file_tags
    op.drop_column('file_tags', 'updated_at')
    op.drop_column('file_tags', 'created_at')
    op.drop_column('file_tags', 'priority')

    # Drop columns from tags
    op.drop_column('tags', 'updated_at')
    op.drop_column('tags', 'created_at')
