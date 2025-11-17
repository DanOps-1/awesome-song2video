from uuid import uuid4

import pytest

from src.domain.models.render_job import RenderJob
from src.infra.persistence.repositories.render_job_repository import RenderJobRepository


@pytest.mark.asyncio
async def test_render_job_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = RenderJobRepository()
    job = RenderJob(
        id=str(uuid4()),
        mix_request_id="mix",
        job_status="queued",
        ffmpeg_script="",
    )
    await repo.save(job)

    async def fake_render(*args, **kwargs):
        await repo.mark_success(job.id, output_asset_id="s3://video.mp4")

    monkeypatch.setattr("src.workers.render_worker._run_ffmpeg", fake_render)
    await fake_render()
    refreshed = await repo.get(job.id)
    assert refreshed is not None
    assert refreshed.job_status == "success"
