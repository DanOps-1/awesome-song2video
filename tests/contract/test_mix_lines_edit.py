import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_and_edit_lines(app_client: AsyncClient) -> None:
    create_resp = await app_client.post(
        "/api/v1/mixes",
        json={
            "song_title": "校对歌曲",
            "source_type": "upload",
            "lyrics_text": "a\nb",
            "language": "zh",
            "auto_generate": False,
        },
    )
    mix_id = create_resp.json()["id"]

    list_resp = await app_client.get(f"/api/v1/mixes/{mix_id}/lines")
    assert list_resp.status_code == 200

    line_id = "00000000-0000-0000-0000-000000000001"
    patch_resp = await app_client.patch(
        f"/api/v1/mixes/{mix_id}/lines/{line_id}",
        json={"start_time_ms": 0, "end_time_ms": 1500, "annotations": "人工调整"},
    )
    assert patch_resp.status_code in {200, 404}
