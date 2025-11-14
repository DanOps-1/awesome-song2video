from typing import Any

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_preview_manifest(app_client: AsyncClient) -> None:
    payload: dict[str, Any] = {
        "song_title": "预览测试",
        "source_type": "upload",
        "lyrics_text": "第一句\n第二句",
        "language": "zh",
        "auto_generate": True,
    }
    create = await app_client.post("/api/v1/mixes", json=payload)
    mix = create.json()
    mix_id = mix["id"]

    trigger = await app_client.post(f"/api/v1/mixes/{mix_id}/generate-timeline")
    assert trigger.status_code == 202

    manifest_resp = await app_client.get(f"/api/v1/mixes/{mix_id}/preview")
    assert manifest_resp.status_code == 200
    manifest = manifest_resp.json()["manifest"]
    assert len(manifest) == 2
    entry = manifest[0]
    assert entry["source_video_id"]
    line_id = entry["line_id"]

    line_resp = await app_client.get(f"/api/v1/mixes/{mix_id}/preview/{line_id}")
    assert line_resp.status_code == 200
    assert line_resp.json()["line_id"] == line_id
