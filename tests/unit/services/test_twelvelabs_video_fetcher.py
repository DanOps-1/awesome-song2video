from __future__ import annotations

from pathlib import Path

import pytest

from src.infra.config.settings import AppSettings
from src.services.matching.twelvelabs_video_fetcher import TwelveLabsVideoFetcher


class _DummyResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:  # noqa: D401
        """模拟 httpx Response 成功。"""
        return None

    def json(self) -> dict:
        return self._payload


def _build_settings(tmp_path: Path, live: bool) -> AppSettings:
    return AppSettings(
        tl_api_key="test-key",
        tl_index_id="idx",
        tl_live_enabled=live,
        tl_api_base_url="https://api.twelvelabs.io",
        postgres_dsn="sqlite+aiosqlite://",
        redis_url="redis://localhost:6379/0",
        media_bucket="bucket",
        minio_endpoint="http://localhost:9000",
        video_asset_dir=tmp_path.as_posix(),
    )


def test_fetch_clip_downloads_segment_without_persisting_whole_video(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings(tmp_path, live=True)
    fetcher = TwelveLabsVideoFetcher(settings=settings)

    calls: list[str] = []

    def fake_get(url, headers, timeout):
        calls.append(url)
        return _DummyResponse({"hls": {"video_url": "https://cdn.example/stream.m3u8"}})

    def fake_run(cmd, check, stdout, stderr):
        target = Path(cmd[-1])
        target.write_bytes(b"clip-data")

    monkeypatch.setattr("httpx.get", fake_get)
    monkeypatch.setattr("subprocess.run", fake_run)

    clip_path = tmp_path / "clip.mp4"
    resolved = fetcher.fetch_clip("remote_vid", 1000, 2500, clip_path)
    assert resolved == clip_path
    assert clip_path.exists()
    assert (tmp_path / "remote_vid.mp4").exists() is False  # 未持久化整段
    assert len(calls) == 1


def test_fetch_clip_falls_back_to_local_when_live_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings(tmp_path, live=False)
    fetcher = TwelveLabsVideoFetcher(settings=settings)

    local_video = tmp_path / "local_vid.mp4"
    local_video.write_bytes(b"full-video")

    def fake_run(cmd, check, stdout, stderr):
        target = Path(cmd[-1])
        target.write_bytes(b"local-clip")

    monkeypatch.setattr("subprocess.run", fake_run)

    clip_path = tmp_path / "clip_local.mp4"
    resolved = fetcher.fetch_clip("local_vid", 0, 1000, clip_path)
    assert resolved == clip_path
    assert clip_path.read_bytes() == b"local-clip"
