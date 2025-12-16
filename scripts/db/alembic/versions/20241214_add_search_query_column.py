"""add search_query column to video_segment_matches

Revision ID: 20241214_add_search_query
Revises: 20241119_add_render_clip_stats
Create Date: 2024-12-14 10:00:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20241214_add_search_query"
down_revision = "20241119_add_render_clip_stats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "video_segment_matches",
        sa.Column("search_query", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("video_segment_matches", "search_query")
