from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_render_config(app_client: AsyncClient) -> None:
    resp = await app_client.get("/render/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["max_parallelism"] >= 1
    assert data["per_video_limit"] >= 1


@pytest.mark.asyncio
async def test_patch_render_config(app_client: AsyncClient) -> None:
    resp = await app_client.patch(
        "/render/config",
        json={"max_parallelism": 5, "per_video_limit": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["max_parallelism"] == 5
    assert data["per_video_limit"] == 2

    # subsequent GET reflects new value
    fetch = await app_client.get("/render/config")
    assert fetch.json()["max_parallelism"] == 5
