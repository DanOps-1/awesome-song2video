import asyncio

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_timeline_performance_under_load(app_client: AsyncClient) -> None:
    payload = {
        "song_title": "压力测试",
        "source_type": "upload",
        "lyrics_text": "\n".join([f"line {i}" for i in range(30)]),
        "language": "zh",
        "auto_generate": False,
    }

    tasks = [app_client.post("/api/v1/mixes", json=payload) for _ in range(10)]
    responses = await asyncio.gather(*tasks)
    assert all(resp.status_code == 201 for resp in responses)
