#!/usr/bin/env python
"""调试专用 Demo：使用 20 秒短音频快速测试渲染流程。

用法：
    python scripts/dev/run_audio_demo_debug.py

特点：
- 使用 tom_debug_20s.mp3（20秒）而非完整音频（3分钟）
- 快速测试候选片段回退、SDK 集成等新功能
- 保留完整日志输出
"""
# ruff: noqa: E402

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient

# 将项目根目录添加到 Python 路径
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.api.main import app
from src.infra.config.settings import get_settings
from src.infra.observability.otel import configure_logging
from src.infra.persistence.database import init_engine, init_models

# 配置日志（在其他操作之前）
configure_logging()

DB_PATH = Path("test_audio_demo.db")


def _patch_render_worker_tempdir() -> None:
    """将 render_worker 临时目录指向 artifacts，便于调试检查。"""
    import src.workers.render_worker as render_module

    def patched_ensure_tmp_root() -> Path:
        root = Path("artifacts/render_tmp")
        root.mkdir(parents=True, exist_ok=True)
        return root

    render_module.ensure_tmp_root = patched_ensure_tmp_root


async def _lock_all_lines(client: AsyncClient, mix_id: str) -> list[dict[str, Any]]:
    """锁定所有歌词行用于渲染。"""
    resp = await client.get(f"/api/v1/mixes/{mix_id}/lines")
    resp.raise_for_status()
    locked: list[dict[str, Any]] = []
    for line in resp.json()["lines"]:
        candidates = line.get("candidates") or []
        payload: dict[str, Any] = {
            "start_time_ms": line["start_time_ms"],
            "end_time_ms": line["end_time_ms"],
            "annotations": "Debug auto lock",
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
    audio_path = (Path(settings.audio_asset_dir) / "tom_debug_20s.mp3").resolve()
    if not audio_path.exists():  # pragma: no cover - 安全检查
        raise FileNotFoundError(
            f"未找到调试音频：{audio_path}\n"
            f"请运行: ffmpeg -y -i media/audio/tom.mp3 -t 20 -c copy {audio_path}"
        )

    if DB_PATH.exists():
        DB_PATH.unlink()
    init_engine(settings.postgres_dsn)
    await init_models()
    _patch_render_worker_tempdir()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://demo.local") as client:
        mix_payload = {
            "song_title": "Debug 20s Test",
            "artist": "Debug Artist",
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

        # 锁定所有歌词行
        locked_lines = await _lock_all_lines(client, mix_id)
        print(f"已锁定 {len(locked_lines)} 行歌词用于渲染")

        resp = await client.post(
            f"/api/v1/mixes/{mix_id}/render",
            json={"resolution": "720p", "frame_rate": 30},
        )
        resp.raise_for_status()
        result = resp.json()
        job_id = result["job_id"]

        # 等待渲染完成（同步模式下应该立即完成）
        # 为了健壮性，添加轮询检查
        import time
        max_wait = 60  # 最多等 60 秒
        poll_interval = 0.5
        elapsed = 0.0

        while elapsed < max_wait:
            resp = await client.get(f"/api/v1/mixes/{mix_id}/render", params={"job_id": job_id})
            resp.raise_for_status()
            status_data = resp.json()
            status = status_data.get("status")

            if status in ("completed", "failed"):
                break

            time.sleep(poll_interval)
            elapsed += poll_interval

        # 从数据库查询最终输出路径
        from src.infra.persistence.repositories.render_job_repository import RenderJobRepository
        job_repo = RenderJobRepository()
        job = await job_repo.get(job_id)

        output_path = None
        if job and job.output_asset_id:
            output_path = job.output_asset_id

        print(f"\n{'=' * 60}")
        print("调试测试完成！")
        print(f"{'=' * 60}")
        print(f"Mix ID: {mix_id}")
        print(f"Job ID: {job_id}")
        print(f"状态: {status}")
        print(f"输出视频: {output_path or '未找到'}")
        print("音频时长: 20 秒")
        print(f"{'=' * 60}\n")

        return {"job_id": job_id, "status": status, "output_path": output_path}


def main() -> None:
    print(f"\n{'=' * 60}")
    print("启动调试测试 (20秒音频)")
    print(f"{'=' * 60}\n")

    result = asyncio.run(run_demo())

    if result.get("output_path"):
        output_path = Path(result["output_path"])
        if output_path.exists():
            print(f"✓ 视频生成成功: {output_path}")
            print(f"  文件大小: {output_path.stat().st_size / (1024*1024):.2f} MB")
        else:
            print(f"✗ 视频文件未找到: {output_path}")
    else:
        print("✗ 渲染失败")


if __name__ == "__main__":
    main()
