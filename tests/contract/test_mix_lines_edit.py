import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_lines_empty(app_client: AsyncClient) -> None:
    """测试获取歌词行列表 - 新创建的 mix 应返回空列表。

    注意：创建 mix 时提供的 lyrics_text 只是存储原始歌词，
    不会自动创建 LyricLine 记录。LyricLine 需要通过：
    - import-lyrics 端点导入
    - 或 fetch-lyrics 端点从在线服务获取
    """
    create_resp = await app_client.post(
        "/api/v1/mixes",
        json={
            "song_title": "校对歌曲",
            "source_type": "upload",
            "audio_asset_id": "test-audio-id",
            "lyrics_text": "a\nb",
            "language": "zh",
            "auto_generate": False,
        },
    )
    assert create_resp.status_code == 201
    mix_id = create_resp.json()["id"]

    # 获取歌词行列表 - 新创建的 mix 应返回空列表
    list_resp = await app_client.get(f"/api/v1/mixes/{mix_id}/lines")
    assert list_resp.status_code == 200

    lines = list_resp.json()["lines"]
    # 新创建的 mix 没有 LyricLine 记录
    assert lines == []


@pytest.mark.asyncio
async def test_edit_nonexistent_line(app_client: AsyncClient) -> None:
    """测试编辑不存在的歌词行应返回 404。"""
    create_resp = await app_client.post(
        "/api/v1/mixes",
        json={
            "song_title": "测试歌曲",
            "source_type": "upload",
            "audio_asset_id": "test-audio-id",
            "lyrics_text": "测试",
            "language": "zh",
            "auto_generate": False,
        },
    )
    assert create_resp.status_code == 201
    mix_id = create_resp.json()["id"]

    # 编辑不存在的行应返回错误（400 或 404）
    patch_resp = await app_client.patch(
        f"/api/v1/mixes/{mix_id}/lines/nonexistent-line-id",
        json={"start_time_ms": 0, "end_time_ms": 1500, "annotations": "人工调整"},
    )
    assert patch_resp.status_code in {400, 404}
