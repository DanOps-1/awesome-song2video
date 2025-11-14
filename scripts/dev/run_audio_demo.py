#!/usr/bin/env python
"""运行端到端 Demo：读取 media/audio/tom.mp3，生成英文歌词混剪视频。"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient

import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:  # pragma: no cover - 路径注入
    sys.path.insert(0, str(REPO_ROOT))

from src.api.main import app
from src.infra.config.settings import get_settings
from src.infra.persistence.database import init_engine, init_models
from src.infra.persistence.repositories.render_job_repository import RenderJobRepository
from src.workers import render_worker


ARTIFACT_DIR = Path("artifacts/renders")
TEMP_OUTPUT_DIR = Path("artifacts/render_tmp")
DB_PATH = Path("dev.db")


def _patch_render_worker_tempdir() -> None:
    TEMP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    class PersistentTempDir:
        def __init__(self) -> None:
            self.name = tempfile.mkdtemp(prefix="job_", dir=TEMP_OUTPUT_DIR.as_posix())

        def __enter__(self) -> str:  # pragma: no cover - 仅 Demo 使用
            return self.name

        def __exit__(self, exc_type, exc, tb) -> bool:  # pragma: no cover - 仅 Demo 使用
            return False

    render_worker.tempfile.TemporaryDirectory = PersistentTempDir  # type: ignore[attr-defined]


async def _lock_all_lines(client: AsyncClient, mix_id: str) -> list[dict[str, Any]]:
    resp = await client.get(f"/api/v1/mixes/{mix_id}/lines")
    resp.raise_for_status()
    locked: list[dict[str, Any]] = []
    for line in resp.json()["lines"]:
        candidates = line.get("candidates") or []
        payload: dict[str, Any] = {
            "start_time_ms": line["start_time_ms"],
            "end_time_ms": line["end_time_ms"],
            "annotations": "Demo auto lock",
        }
        if candidates:
            payload["selected_segment_id"] = candidates[0]["id"]
        resp = await client.patch(
            f"/api/v1/mixes/{mix_id}/lines/{line['id']}",
            json=payload,
        )
        resp.raise_for_status()
        locked.append(resp.json())
    return locked


async def run_demo() -> dict[str, Any]:
    settings = get_settings()
    audio_path = (Path(settings.audio_asset_dir) / "tom.mp3").resolve()
    if not audio_path.exists():  # pragma: no cover - 安全检查
        raise FileNotFoundError(f"未找到示例音频：{audio_path}")

    if DB_PATH.exists():
        DB_PATH.unlink()
    init_engine(settings.postgres_dsn)
    await init_models()
    _patch_render_worker_tempdir()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://demo.local") as client:
        mix_payload = {
            "song_title": "Tom English Demo",
            "artist": "Demo Singer",
            "source_type": "upload",
            "audio_asset_id": audio_path.as_posix(),
            "language": "en",
            "auto_generate": True,
        }
        resp = await client.post("/api/v1/mixes", json=mix_payload)
        resp.raise_for_status()
        mix_id = resp.json()["id"]

        resp = await client.post(f"/api/v1/mixes/{mix_id}/generate-timeline")
        resp.raise_for_status()

        locked_lines = await _lock_all_lines(client, mix_id)

        resp = await client.post(
            f"/api/v1/mixes/{mix_id}/render",
            json={"resolution": "1080p", "frame_rate": 25},
        )
        resp.raise_for_status()
        job_id = resp.json()["job_id"]

        resp = await client.get(
            f"/api/v1/mixes/{mix_id}/render",
            params={"job_id": job_id},
        )
        resp.raise_for_status()
        job_status = resp.json()["status"]

    repo = RenderJobRepository()
    job = await repo.get(job_id)
    output_path = Path(job.output_asset_id) if job and job.output_asset_id else None

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    final_video = None
    final_subtitle = None
    if output_path and output_path.exists():
        final_video = ARTIFACT_DIR / f"{job_id}.mp4"
        shutil.copy2(output_path, final_video)
        subtitle_candidate = output_path.with_suffix(".srt")
        if subtitle_candidate.exists():
            final_subtitle = ARTIFACT_DIR / f"{job_id}.srt"
            shutil.copy2(subtitle_candidate, final_subtitle)

    return {
        "mix_id": mix_id,
        "job_id": job_id,
        "job_status": job_status,
        "locked_lines": len(locked_lines),
        "video_path": str(final_video) if final_video else None,
        "subtitle_path": str(final_subtitle) if final_subtitle else None,
    }


def main() -> None:
    result = asyncio.run(run_demo())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
