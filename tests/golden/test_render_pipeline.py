import json
from pathlib import Path

import pytest

from src.pipelines.rendering.ffmpeg_script_builder import FFMpegScriptBuilder, RenderLine


def _dummy_lines() -> list[RenderLine]:
    return [
        RenderLine(
            source_video_id="demo",
            start_time_ms=0,
            end_time_ms=2_000,
            lyrics="第一句",
            lyric_start_ms=0,
            lyric_end_ms=2_000,
        ),
        RenderLine(
            source_video_id="demo",
            start_time_ms=2_000,
            end_time_ms=4_000,
            lyrics="第二句",
            lyric_start_ms=2_000,
            lyric_end_ms=4_000,
        ),
    ]


@pytest.mark.parametrize("resolution", ["1080p", "720p"])
def test_ffmpeg_script_builder_outputs_edl(tmp_path: Path, resolution: str) -> None:
    builder = FFMpegScriptBuilder(resolution=resolution, frame_rate=25)
    script = builder.build_script(lines=_dummy_lines())
    assert "filter_complex" in script

    edl_path = tmp_path / "timeline.json"
    builder.write_edl(lines=_dummy_lines(), output_path=edl_path)
    data = json.loads(edl_path.read_text())
    assert len(data["lines"]) == 2
