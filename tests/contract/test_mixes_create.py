from typing import Any

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_mix_and_trigger_generation(app_client: AsyncClient) -> None:
    payload: dict[str, Any] = {
        "song_title": "示例歌曲",
        "source_type": "upload",
        "lyrics_text": "第一句\n第二句",
        "language": "zh",
        "auto_generate": True,
    }

    response = await app_client.post("/api/v1/mixes", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["song_title"] == payload["song_title"]

    mix_id = data["id"]
    trigger = await app_client.post(f"/api/v1/mixes/{mix_id}/generate-timeline")
    assert trigger.status_code == 202
    assert "trace_id" in trigger.json()
