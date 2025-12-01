from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import uuid4

from arq.connections import create_pool
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from src.domain.models.song_mix import SongMixRequest
from src.infra.config.settings import get_settings
from src.infra.persistence.repositories.song_mix_repository import SongMixRepository
from src.workers import redis_settings
from src.workers.timeline_worker import build_timeline, transcribe_lyrics, match_videos


router = APIRouter(prefix="/api/v1/mixes", tags=["mixes"])
repo = SongMixRepository()
settings = get_settings()


class MixCreateRequest(BaseModel):
    song_title: str = Field(..., min_length=1, max_length=128)
    artist: str | None = None
    source_type: str = Field(..., pattern="^(upload|catalog|manual)$")
    audio_asset_id: str | None = None
    lyrics_text: str | None = None
    language: str = "auto"
    auto_generate: bool = True


class LyricLineResponse(BaseModel):
    """歌词行响应。"""
    id: str
    line_no: int
    original_text: str
    start_time_ms: int
    end_time_ms: int
    status: str


class MixResponse(BaseModel):
    id: str
    song_title: str
    timeline_status: str
    timeline_progress: float = 0.0
    lyrics_confirmed: bool = False
    render_status: str


class MixDetailResponse(MixResponse):
    """混剪任务详情，包含歌词行。"""
    lines: list[LyricLineResponse] = []


class UpdateLineRequest(BaseModel):
    """更新歌词行请求。

    支持两种操作：
    - 提供 text: 更新歌词文本（用于歌词校对阶段）
    - 提供 selected_segment_id: 锁定选中的视频片段（用于视频确认阶段）
    """
    text: str | None = Field(None, min_length=1, max_length=500)
    selected_segment_id: str | None = None


class AddLineRequest(BaseModel):
    """添加歌词行请求。"""
    text: str = Field(..., min_length=1, max_length=500, description="歌词文本")
    start_time_ms: int = Field(..., ge=0, description="开始时间（毫秒）")
    end_time_ms: int = Field(..., ge=0, description="结束时间（毫秒）")


@router.post("", status_code=201, response_model=MixResponse)
async def create_mix(payload: MixCreateRequest) -> MixResponse:
    # 手动模式必须提供歌词，其他模式必须提供音频
    if payload.source_type == "manual":
        if not payload.lyrics_text:
            raise HTTPException(status_code=400, detail="手动模式必须提供歌词")
    elif not payload.audio_asset_id:
        raise HTTPException(status_code=400, detail="必须提供音频文件")

    mix = SongMixRequest(
        id=str(uuid4()),
        song_title=payload.song_title,
        artist=payload.artist,
        source_type=payload.source_type,
        audio_asset_id=payload.audio_asset_id,
        lyrics_text=payload.lyrics_text or "",
        language=payload.language,
        owner_id="system",
    )
    saved = await repo.create_request(mix)
    return MixResponse(
        id=saved.id,
        song_title=saved.song_title,
        timeline_status=saved.timeline_status,
        timeline_progress=saved.timeline_progress,
        lyrics_confirmed=saved.lyrics_confirmed,
        render_status=saved.render_status,
    )


@router.get("/{mix_id}", response_model=MixDetailResponse)
async def get_mix(mix_id: Annotated[str, Path(description="混剪任务 ID")]) -> MixDetailResponse:
    """获取混剪任务状态，包含时间线生成进度和歌词行。"""
    mix = await repo.get_request(mix_id)
    if mix is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 获取歌词行
    lines = await repo.list_lines(mix_id)
    line_responses = [
        LyricLineResponse(
            id=line.id,
            line_no=line.line_no,
            original_text=line.original_text,
            start_time_ms=line.start_time_ms,
            end_time_ms=line.end_time_ms,
            status=line.status,
        )
        for line in lines
    ]

    return MixDetailResponse(
        id=mix.id,
        song_title=mix.song_title,
        timeline_status=mix.timeline_status,
        timeline_progress=mix.timeline_progress,
        lyrics_confirmed=mix.lyrics_confirmed,
        render_status=mix.render_status,
        lines=line_responses,
    )


@router.post("/{mix_id}/transcribe", status_code=202)
async def trigger_transcription(
    mix_id: Annotated[str, Path(description="混剪任务 ID")]
) -> dict[str, str]:
    """触发歌词识别（阶段1）。

    仅进行 Whisper 识别，不进行视频匹配。
    完成后状态变为 transcribed，等待用户确认歌词。
    """
    mix = await repo.get_request(mix_id)
    if mix is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    trace_id = str(uuid4())
    if settings.enable_async_queue:
        pool = await create_pool(redis_settings())
        await pool.enqueue_job("transcribe_lyrics", mix_id)
    else:
        asyncio.create_task(transcribe_lyrics({}, mix_id))

    return {"trace_id": trace_id, "message": "已开始歌词识别"}


class ImportLyricsRequest(BaseModel):
    """导入歌词请求。"""
    lyrics_text: str = Field(..., min_length=1, description="歌词文本，每行一句")


@router.post("/{mix_id}/import-lyrics", status_code=200)
async def import_lyrics(
    mix_id: Annotated[str, Path(description="混剪任务 ID")],
    payload: ImportLyricsRequest,
) -> dict[str, str]:
    """导入用户提供的歌词（跳过 Whisper 识别）。

    将用户提供的歌词文本解析为歌词行，并根据音频时长均匀分配时间戳。
    完成后状态变为 transcribed，等待用户确认歌词。
    """
    import subprocess
    from pathlib import Path as FilePath
    from src.domain.models.song_mix import LyricLine

    mix = await repo.get_request(mix_id)
    if mix is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if mix.timeline_status not in ("pending", "error"):
        raise HTTPException(status_code=400, detail="任务状态不允许导入歌词")

    # 解析歌词文本
    lines_text = [line.strip() for line in payload.lyrics_text.strip().split("\n") if line.strip()]
    if not lines_text:
        raise HTTPException(status_code=400, detail="歌词不能为空")

    # 获取音频时长
    audio_duration_ms = 180000  # 默认 3 分钟
    if mix.audio_asset_id:
        audio_dir = FilePath(settings.audio_asset_dir)
        for ext in [".mp3", ".wav", ".flac", ".m4a", ".aac"]:
            audio_file = audio_dir / f"{mix.audio_asset_id}{ext}"
            if audio_file.exists():
                try:
                    result = subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_file)],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        audio_duration_ms = int(float(result.stdout.strip()) * 1000)
                except Exception:
                    pass
                break

    # 均匀分配时间戳
    line_duration_ms = audio_duration_ms // len(lines_text)
    lyric_lines: list[LyricLine] = []

    for index, text in enumerate(lines_text, start=1):
        start_ms = (index - 1) * line_duration_ms
        end_ms = index * line_duration_ms
        lyric_lines.append(
            LyricLine(
                id=str(uuid4()),
                mix_request_id=mix_id,
                line_no=index,
                original_text=text,
                start_time_ms=start_ms,
                end_time_ms=end_ms,
                status="pending",
            )
        )

    # 保存歌词行
    await repo.bulk_insert_lines(lyric_lines)
    await repo.update_timeline_status(mix_id, "transcribed")

    return {"message": f"已导入 {len(lyric_lines)} 行歌词"}


@router.patch("/{mix_id}/lines/{line_id}")
async def update_line(
    mix_id: Annotated[str, Path(description="混剪任务 ID")],
    line_id: Annotated[str, Path(description="歌词行 ID")],
    payload: UpdateLineRequest,
) -> LyricLineResponse:
    """更新歌词行。

    支持两种操作：
    - 提供 text: 更新歌词文本（歌词校对阶段）
    - 提供 selected_segment_id: 锁定选中的视频片段（视频确认阶段）
    """
    mix = await repo.get_request(mix_id)
    if mix is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 验证请求参数
    if payload.text is None and payload.selected_segment_id is None:
        raise HTTPException(status_code=400, detail="请提供 text 或 selected_segment_id")

    try:
        # 操作1：更新歌词文本
        if payload.text is not None:
            if mix.lyrics_confirmed:
                raise HTTPException(status_code=400, detail="歌词已确认，无法修改")
            line = await repo.update_line_text(line_id, payload.text)
        # 操作2：锁定选中的视频片段
        else:
            line = await repo.lock_line_segment(line_id, payload.selected_segment_id)

        return LyricLineResponse(
            id=line.id,
            line_no=line.line_no,
            original_text=line.original_text,
            start_time_ms=line.start_time_ms,
            end_time_ms=line.end_time_ms,
            status=line.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e) or "歌词行不存在")


@router.post("/{mix_id}/lines", status_code=201, response_model=LyricLineResponse)
async def add_line(
    mix_id: Annotated[str, Path(description="混剪任务 ID")],
    payload: AddLineRequest,
) -> LyricLineResponse:
    """添加新的歌词行，根据时间自动排序到正确位置。

    仅在歌词校对阶段（transcribed 状态且未确认）可用。
    """
    mix = await repo.get_request(mix_id)
    if mix is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if mix.lyrics_confirmed:
        raise HTTPException(status_code=400, detail="歌词已确认，无法添加")

    if mix.timeline_status not in ("transcribed", "pending"):
        raise HTTPException(status_code=400, detail="当前状态不允许添加歌词")

    if payload.end_time_ms <= payload.start_time_ms:
        raise HTTPException(status_code=400, detail="结束时间必须大于开始时间")

    try:
        line = await repo.add_line(
            mix_id=mix_id,
            text=payload.text,
            start_time_ms=payload.start_time_ms,
            end_time_ms=payload.end_time_ms,
        )
        return LyricLineResponse(
            id=line.id,
            line_no=line.line_no,
            original_text=line.original_text,
            start_time_ms=line.start_time_ms,
            end_time_ms=line.end_time_ms,
            status=line.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{mix_id}/lines/{line_id}", status_code=200)
async def delete_line(
    mix_id: Annotated[str, Path(description="混剪任务 ID")],
    line_id: Annotated[str, Path(description="歌词行 ID")],
) -> dict[str, str]:
    """删除歌词行。

    仅在歌词校对阶段（transcribed 状态且未确认）可用。
    """
    mix = await repo.get_request(mix_id)
    if mix is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if mix.lyrics_confirmed:
        raise HTTPException(status_code=400, detail="歌词已确认，无法删除")

    if mix.timeline_status not in ("transcribed", "pending"):
        raise HTTPException(status_code=400, detail="当前状态不允许删除歌词")

    try:
        await repo.delete_line(line_id)
        return {"message": "歌词行已删除"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{mix_id}/confirm-lyrics", status_code=200)
async def confirm_lyrics(
    mix_id: Annotated[str, Path(description="混剪任务 ID")]
) -> dict[str, str]:
    """确认歌词。

    确认后不可再修改歌词，可以触发视频匹配。
    """
    mix = await repo.get_request(mix_id)
    if mix is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if mix.timeline_status != "transcribed":
        raise HTTPException(status_code=400, detail="歌词尚未识别完成")

    if mix.lyrics_confirmed:
        raise HTTPException(status_code=400, detail="歌词已确认")

    await repo.confirm_lyrics(mix_id)
    return {"message": "歌词已确认"}


@router.post("/{mix_id}/match-videos", status_code=202)
async def trigger_video_matching(
    mix_id: Annotated[str, Path(description="混剪任务 ID")]
) -> dict[str, str]:
    """触发视频匹配（阶段2）。

    前提条件：歌词已确认 (lyrics_confirmed = True)。
    完成后状态变为 generated，可以进行预览和渲染。
    """
    mix = await repo.get_request(mix_id)
    if mix is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if not mix.lyrics_confirmed:
        raise HTTPException(status_code=400, detail="请先确认歌词")

    if mix.timeline_status == "matching":
        raise HTTPException(status_code=400, detail="视频匹配进行中")

    if mix.timeline_status == "generated":
        raise HTTPException(status_code=400, detail="视频已匹配完成")

    trace_id = str(uuid4())
    if settings.enable_async_queue:
        pool = await create_pool(redis_settings())
        await pool.enqueue_job("match_videos", mix_id)
    else:
        asyncio.create_task(match_videos({}, mix_id))

    return {"trace_id": trace_id, "message": "已开始视频匹配"}


@router.post("/{mix_id}/generate-timeline", status_code=202)
async def trigger_generation(
    mix_id: Annotated[str, Path(description="混剪任务 ID")]
) -> dict[str, str]:
    """触发完整时间线生成（兼容旧流程）。

    一次性完成 Whisper 识别 + 视频匹配。
    新流程请使用 /transcribe -> /confirm-lyrics -> /match-videos。
    """
    mix = await repo.get_request(mix_id)
    if mix is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    trace_id = str(uuid4())
    if settings.enable_async_queue:
        pool = await create_pool(redis_settings())
        await pool.enqueue_job("build_timeline", mix_id)
    else:
        asyncio.create_task(build_timeline({}, mix_id))

    return {"trace_id": trace_id, "message": "已进入匹配队列"}
