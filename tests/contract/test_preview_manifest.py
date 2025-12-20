from typing import Any

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_preview_manifest_pending(app_client: AsyncClient) -> None:
    """测试创建 mix 并触发 timeline 生成。

    注意：在测试环境中没有运行 worker，所以 timeline 不会真正生成。
    此测试验证：
    1. 创建 mix 成功
    2. 触发生成返回 202 (已接受)
    3. 在 timeline 未生成时，preview 返回 404 (正确行为)
    """
    payload: dict[str, Any] = {
        "song_title": "预览测试",
        "source_type": "upload",
        "audio_asset_id": "test-audio-id",
        "lyrics_text": "第一句\n第二句",
        "language": "zh",
        "auto_generate": True,
    }
    create = await app_client.post("/api/v1/mixes", json=payload)
    assert create.status_code == 201
    mix = create.json()
    mix_id = mix["id"]

    # 触发 timeline 生成 - 返回 202 表示已接受异步处理
    trigger = await app_client.post(f"/api/v1/mixes/{mix_id}/generate-timeline")
    assert trigger.status_code == 202

    # 在没有 worker 的测试环境中，timeline 不会立即生成
    # API 应返回 404 表示 timeline 尚未准备好
    manifest_resp = await app_client.get(f"/api/v1/mixes/{mix_id}/preview")
    assert manifest_resp.status_code == 404
