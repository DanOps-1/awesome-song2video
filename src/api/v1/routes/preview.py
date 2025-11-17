"""Preview manifest API 路由。

提供歌词混剪的预览清单与指标查询。
"""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, HTTPException, Path

from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
from src.services.preview.preview_service import preview_service


logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/mixes/{mix_id}/preview", tags=["preview"])


@router.get("", response_model=None)
async def get_preview_manifest(
    mix_id: Annotated[str, Path(description="混剪任务 ID")],
) -> dict[str, Any]:
    """获取混剪任务的时间线 manifest 与 preview 指标。

    返回完整的歌词-视频映射清单,包含:
    - manifest: 每行歌词对应的视频片段信息
    - metrics: 对齐质量指标(平均偏差、最大偏差、fallback 数量等)

    Args:
        mix_id: 混剪任务 ID

    Returns:
        包含 manifest 和 metrics 的 JSON 响应

    Raises:
        HTTPException: 404 - timeline 未生成或 mix 不存在
    """
    logger.info("preview.api.get_manifest", mix_id=mix_id)

    try:
        # 检查 mix 是否存在
        repo = SongMixRepository()
        mix = await repo.get_request(mix_id)
        if mix is None:
            logger.warning("preview.api.mix_not_found", mix_id=mix_id)
            raise HTTPException(status_code=404, detail="mix not found")

        # 检查 timeline 是否已生成
        if mix.timeline_status != "generated":
            logger.warning(
                "preview.api.timeline_not_ready",
                mix_id=mix_id,
                timeline_status=mix.timeline_status,
            )
            raise HTTPException(
                status_code=404, detail=f"timeline not ready (status: {mix.timeline_status})"
            )

        # 构建 manifest
        result = await preview_service.build_manifest(mix_id, owner_id=mix.owner_id)

        if not result["manifest"]:
            logger.warning("preview.api.empty_manifest", mix_id=mix_id)
            raise HTTPException(status_code=404, detail="manifest is empty")

        logger.info(
            "preview.api.manifest_returned",
            mix_id=mix_id,
            line_count=len(result["manifest"]),
            fallback_count=result["metrics"]["fallback_count"],
        )

        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("preview.api.unexpected_error", mix_id=mix_id, error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="internal server error") from exc


@router.get("/{line_id}", response_model=None)
async def get_line_preview(
    mix_id: Annotated[str, Path(description="混剪任务 ID")],
    line_id: Annotated[str, Path(description="歌词行 ID")],
) -> dict[str, Any]:
    """获取单句歌词的片段映射。

    Args:
        mix_id: 混剪任务 ID
        line_id: 歌词行 ID

    Returns:
        单行 manifest entry

    Raises:
        HTTPException: 404 - line 不存在
    """
    logger.info("preview.api.get_line", mix_id=mix_id, line_id=line_id)

    try:
        result = await preview_service.get_line_preview(mix_id, line_id)
        logger.info(
            "preview.api.line_returned",
            mix_id=mix_id,
            line_id=line_id,
            fallback=result.get("fallback", False),
        )
        return result
    except ValueError as exc:
        logger.warning("preview.api.line_not_found", mix_id=mix_id, line_id=line_id)
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(
            "preview.api.unexpected_error",
            mix_id=mix_id,
            line_id=line_id,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="internal server error") from exc
