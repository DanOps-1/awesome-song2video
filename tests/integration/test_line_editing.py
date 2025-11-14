from uuid import uuid4

import pytest

from src.domain.models.song_mix import LyricLine, SongMixRequest
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
from src.services.timeline_editor import TimelineEditor


@pytest.mark.asyncio
async def test_timeline_editor_updates_audit_log() -> None:
    repo = SongMixRepository()
    mix = SongMixRequest(
        id=str(uuid4()),
        song_title="测试",
        artist="",
        source_type="upload",
        audio_asset_id="obj",
        lyrics_text="第一句",
        language="zh",
        owner_id="tester",
    )
    await repo.create_request(mix)
    line = LyricLine(
        id=str(uuid4()),
        mix_request_id=mix.id,
        line_no=1,
        original_text="第一句",
        start_time_ms=0,
        end_time_ms=1000,
        status="auto_selected",
    )
    await repo.bulk_insert_lines([line])

    editor = TimelineEditor()
    updated = await editor.lock_line(line_id=line.id, annotations="手动调整")
    assert updated["annotations"] == "手动调整"
    assert updated["status"] == "locked"
