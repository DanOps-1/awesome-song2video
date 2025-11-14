from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel

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


@router.get("", response_model=LineListResponse)
async def list_lines(
    mix_id: Annotated[str, Path(description="混剪任务 ID")],
    min_confidence: Annotated[float | None, Query(ge=0, le=1)] = None,
):
    lines = await editor.list_lines(mix_id, min_confidence=min_confidence)
    return {"lines": lines}


@router.patch("/{line_id}", response_model=LineResponse)
async def update_line(
    mix_id: Annotated[str, Path()],
    line_id: Annotated[str, Path()],
    body: LineUpdateRequest,
):
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


@router.post("/{line_id}/search")
async def search_new_segments(
    mix_id: Annotated[str, Path()],
    line_id: Annotated[str, Path()],
    body: SearchRequest,
):
    try:
        candidates = await editor.rerun_search(line_id, prompt_override=body.prompt_override)
    except ValueError as exc:  # noqa: PERF203
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"candidates": candidates}
