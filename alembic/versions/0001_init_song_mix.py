"""初始化歌词语义混剪核心表"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_init_song_mix"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "song_mix_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("song_title", sa.String(length=128), nullable=False),
        sa.Column("artist", sa.String(length=128)),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("audio_asset_id", sa.String(length=255)),
        sa.Column("lyrics_text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("timeline_status", sa.String(length=32), default="pending"),
        sa.Column("render_status", sa.String(length=32), default="idle"),
        sa.Column("priority", sa.Integer(), default=5),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("error_codes", sa.JSON(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "lyric_lines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("mix_request_id", sa.String(length=36), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("translated_text", sa.Text()),
        sa.Column("start_time_ms", sa.Integer(), nullable=False),
        sa.Column("end_time_ms", sa.Integer(), nullable=False),
        sa.Column("auto_confidence", sa.Float(), nullable=True),
        sa.Column("selected_segment_id", sa.String(length=36)),
        sa.Column("status", sa.String(length=32), default="pending"),
        sa.Column("annotations", sa.Text()),
        sa.Column("audit_log", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["mix_request_id"], ["song_mix_requests.id"], ondelete="CASCADE"),
    )
    op.create_unique_constraint("uq_lyric_lines_mix_line", "lyric_lines", ["mix_request_id", "line_no"])

    op.create_table(
        "video_segment_matches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("line_id", sa.String(length=36), nullable=False),
        sa.Column("source_video_id", sa.String(length=128), nullable=False),
        sa.Column("index_id", sa.String(length=64), nullable=False),
        sa.Column("start_time_ms", sa.Integer(), nullable=False),
        sa.Column("end_time_ms", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("preview_url", sa.String(length=255)),
        sa.Column("generated_by", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["line_id"], ["lyric_lines.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "render_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("mix_request_id", sa.String(length=36), nullable=False),
        sa.Column("job_status", sa.String(length=32), nullable=False),
        sa.Column("worker_node", sa.String(length=64)),
        sa.Column("ffmpeg_script", sa.Text(), nullable=False),
        sa.Column("progress", sa.Float(), default=0.0),
        sa.Column("output_asset_id", sa.String(length=255)),
        sa.Column("error_log", sa.Text()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["mix_request_id"], ["song_mix_requests.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("render_jobs")
    op.drop_table("video_segment_matches")
    op.drop_constraint("uq_lyric_lines_mix_line", "lyric_lines", type_="unique")
    op.drop_table("lyric_lines")
    op.drop_table("song_mix_requests")
