"""ensure render clip stats structure

Revision ID: 20241119_add_render_clip_stats
Revises: 0001_init_song_mix
Create Date: 2025-11-19 16:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20241119_add_render_clip_stats"
down_revision = "0001_init_song_mix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE render_jobs
        SET metrics = jsonb_set(
            COALESCE(metrics::jsonb, '{}'::jsonb),
            '{render,clip_stats}',
            COALESCE((metrics::jsonb -> 'render' -> 'clip_stats'), '{}'::jsonb),
            true
        )::json
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE render_jobs
        SET metrics = CASE
            WHEN metrics::jsonb ? 'render'
                 THEN jsonb_set(
                        metrics::jsonb,
                        '{render}',
                        (metrics::jsonb -> 'render') - 'clip_stats'
                    )::json
            ELSE metrics
        END
        """
    )
