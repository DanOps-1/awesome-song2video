from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from src.api.v1.routes import render_config as render_config_route
from src.domain.services import render_config_service
from src.infra.config.settings import get_settings
from src.workers import render_worker

if TYPE_CHECKING:
    from httpx import AsyncClient


class FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, Any]] = []
        self.stored: dict[str, str] = {}

    async def set(self, key: str, value: str) -> None:
        self.stored[key] = value

    async def publish(self, channel: str, value: str) -> None:
        self.published.append((channel, value))


@pytest.mark.asyncio
async def test_render_config_hot_reload(monkeypatch: pytest.MonkeyPatch, app_client: AsyncClient) -> None:
    fake = FakeRedis()
    monkeypatch.setattr(render_config_route.service, "_redis", fake)
    monkeypatch.setattr(render_config_service, "_cached_config", None)

    initial = render_worker.clip_config.max_parallelism

    resp = await app_client.patch(
        "/render/config",
        json={"max_parallelism": initial + 1},
    )
    assert resp.status_code == 200
    assert render_worker.clip_config.max_parallelism == initial + 1
    assert fake.published
    channel, payload = fake.published[-1]
    assert channel == get_settings().render_config_channel
    data = json.loads(payload)
    assert data["max_parallelism"] == initial + 1
