from __future__ import annotations

import asyncio
from pathlib import Path as FilePath
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.services.matching.twelvelabs_video_fetcher import video_fetcher
from src.services.timeline_editor import TimelineEditor


router = APIRouter(prefix="/api/v1/mixes/{mix_id}/lines", tags=["mix-lines"])
editor = TimelineEditor()


class LineResponse(BaseModel):
    id: str
    line_no: int
    original_text: str
    start_time_ms: int
    end_time_ms: int
    auto_confidence: float | None = None
    selected_segment_id: str | None = None
    status: str
    annotations: str | None = None
    candidates: list[dict]
    audit_log: list[dict]


class LineListResponse(BaseModel):
    lines: list[LineResponse]


class LineUpdateRequest(BaseModel):
    start_time_ms: int | None = None
    end_time_ms: int | None = None
    selected_segment_id: str | None = None
    annotations: str | None = None


class SearchRequest(BaseModel):
    prompt_override: str | None = None


class SearchResponse(BaseModel):
    candidates: list[dict]


@router.get("", response_model=LineListResponse)
async def list_lines(
    mix_id: Annotated[str, Path(description="混剪任务 ID")],
    min_confidence: Annotated[float | None, Query(ge=0, le=1)] = None,
) -> dict[str, Any]:
    lines = await editor.list_lines(mix_id, min_confidence=min_confidence)
    return {"lines": lines}


@router.patch("/{line_id}", response_model=LineResponse)
async def update_line(
    mix_id: Annotated[str, Path()],
    line_id: Annotated[str, Path()],
    body: LineUpdateRequest,
) -> dict[str, Any]:
    try:
        updated = await editor.lock_line(
            line_id,
            start_time_ms=body.start_time_ms,
            end_time_ms=body.end_time_ms,
            selected_segment_id=body.selected_segment_id,
            annotations=body.annotations,
        )
    except ValueError as exc:  # noqa: PERF203
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return updated


@router.post("/{line_id}/search", response_model=SearchResponse)
async def search_new_segments(
    mix_id: Annotated[str, Path()],
    line_id: Annotated[str, Path()],
    body: SearchRequest,
) -> dict[str, Any]:
    try:
        candidates = await editor.rerun_search(line_id, prompt_override=body.prompt_override)
    except ValueError as exc:  # noqa: PERF203
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"candidates": candidates}


@router.get("/{line_id}/candidates/{candidate_id}/preview")
async def preview_candidate(
    mix_id: Annotated[str, Path(description="混剪任务 ID")],
    line_id: Annotated[str, Path(description="歌词行 ID")],
    candidate_id: Annotated[str, Path(description="候选片段 ID")],
) -> FileResponse:
    """预览候选视频片段。

    生成并返回候选视频片段的预览文件。
    """
    # 获取歌词行信息
    line = await editor.get_line(line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="歌词行不存在")

    # 找到对应的候选片段
    candidate = None
    for c in line.get("candidates", []):
        if c.get("id") == candidate_id:
            candidate = c
            break

    if candidate is None:
        raise HTTPException(status_code=404, detail="候选片段不存在")

    video_id = candidate.get("source_video_id")
    start_ms = candidate.get("start_time_ms", 0)
    end_ms = candidate.get("end_time_ms", 0)

    if not video_id:
        raise HTTPException(status_code=400, detail="候选片段缺少 video_id")

    # 创建预览文件目录
    preview_dir = FilePath("artifacts/previews")
    preview_dir.mkdir(parents=True, exist_ok=True)

    # 生成预览文件
    preview_path = preview_dir / f"{candidate_id}.mp4"

    # 如果预览文件已存在且不太旧，直接返回
    if preview_path.exists():
        return FileResponse(
            path=str(preview_path),
            media_type="video/mp4",
            filename=f"preview_{candidate_id}.mp4",
        )

    # 异步执行视频下载
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        video_fetcher.fetch_clip,
        video_id,
        start_ms,
        end_ms,
        preview_path,
    )

    if result is None:
        raise HTTPException(status_code=500, detail="视频预览生成失败")

    return FileResponse(
        path=str(preview_path),
        media_type="video/mp4",
        filename=f"preview_{candidate_id}.mp4",
    )
