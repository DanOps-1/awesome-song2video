"""素材管理 Admin API。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import aiofiles
from fastapi import APIRouter, File, HTTPException, Path as PathParam, Query, UploadFile
from pydantic import BaseModel

from src.infra.config.settings import get_settings


router = APIRouter(prefix="/assets", tags=["admin-assets"])
settings = get_settings()


class VideoAsset(BaseModel):
    id: str
    filename: str
    path: str
    size_bytes: int
    created_at: datetime
    index_status: str = "unknown"


class AudioAsset(BaseModel):
    id: str
    filename: str
    path: str
    size_bytes: int
    duration_ms: int | None = None
    created_at: datetime


class VideoListResponse(BaseModel):
    videos: list[VideoAsset]
    total: int
    page: int
    page_size: int


class AudioListResponse(BaseModel):
    audios: list[AudioAsset]
    total: int
    page: int
    page_size: int


class UploadResponse(BaseModel):
    id: str
    filename: str
    path: str
    size_bytes: int


class IndexStatusResponse(BaseModel):
    video_id: str
    index_id: str | None
    status: str
    indexed_at: datetime | None = None


def _scan_video_dir() -> list[VideoAsset]:
    """扫描视频目录获取资产列表。"""
    video_dir = Path(settings.video_asset_dir)
    if not video_dir.exists():
        return []

    videos = []
    for path in video_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
            stat = path.stat()
            videos.append(
                VideoAsset(
                    id=path.stem,
                    filename=path.name,
                    path=str(path),
                    size_bytes=stat.st_size,
                    created_at=datetime.fromtimestamp(stat.st_ctime),
                    index_status="unknown",
                )
            )

    return sorted(videos, key=lambda x: x.created_at, reverse=True)


def _scan_audio_dir() -> list[AudioAsset]:
    """扫描音频目录获取资产列表。"""
    audio_dir = Path(settings.audio_asset_dir)
    if not audio_dir.exists():
        return []

    audios = []
    for path in audio_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in (".mp3", ".wav", ".flac", ".m4a", ".aac"):
            stat = path.stat()
            audios.append(
                AudioAsset(
                    id=path.stem,
                    filename=path.name,
                    path=str(path),
                    size_bytes=stat.st_size,
                    created_at=datetime.fromtimestamp(stat.st_ctime),
                )
            )

    return sorted(audios, key=lambda x: x.created_at, reverse=True)


@router.get("/videos", response_model=VideoListResponse)
async def list_videos(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    keyword: Annotated[str | None, Query()] = None,
) -> VideoListResponse:
    """获取视频资产列表。"""
    videos = _scan_video_dir()

    # 搜索过滤
    if keyword:
        keyword_lower = keyword.lower()
        videos = [v for v in videos if keyword_lower in v.filename.lower()]

    # 分页
    total = len(videos)
    start = (page - 1) * page_size
    end = start + page_size
    page_videos = videos[start:end]

    return VideoListResponse(
        videos=page_videos,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/videos/upload", response_model=UploadResponse)
async def upload_video(file: UploadFile = File(...)) -> UploadResponse:
    """上传视频文件。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # 检查文件类型
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
        raise HTTPException(status_code=400, detail="Unsupported video format")

    # 创建目录
    video_dir = Path(settings.video_asset_dir)
    video_dir.mkdir(parents=True, exist_ok=True)

    # 生成唯一文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(file.filename).stem
    new_filename = f"{stem}_{timestamp}{suffix}"
    file_path = video_dir / new_filename

    # 保存文件
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    stat = file_path.stat()

    return UploadResponse(
        id=file_path.stem,
        filename=new_filename,
        path=str(file_path),
        size_bytes=stat.st_size,
    )


@router.delete("/videos/{video_id}", status_code=204)
async def delete_video(video_id: Annotated[str, PathParam()]) -> None:
    """删除视频文件。"""
    video_dir = Path(settings.video_asset_dir)

    # 查找匹配的文件
    for path in video_dir.rglob("*"):
        if path.is_file() and path.stem == video_id:
            path.unlink()
            return

    raise HTTPException(status_code=404, detail="Video not found")


@router.get("/videos/{video_id}/index-status", response_model=IndexStatusResponse)
async def get_video_index_status(video_id: Annotated[str, PathParam()]) -> IndexStatusResponse:
    """获取视频的 TwelveLabs 索引状态。"""
    # 检查视频是否存在
    video_dir = Path(settings.video_asset_dir)
    video_exists = any(p.stem == video_id for p in video_dir.rglob("*") if p.is_file())

    if not video_exists:
        raise HTTPException(status_code=404, detail="Video not found")

    # TODO: 实际查询 TwelveLabs API 获取索引状态
    # 目前返回模拟状态
    return IndexStatusResponse(
        video_id=video_id,
        index_id=settings.tl_index_id,
        status="indexed" if settings.tl_live_enabled else "unknown",
    )


@router.post("/videos/{video_id}/reindex", status_code=202)
async def reindex_video(video_id: Annotated[str, PathParam()]) -> dict[str, str]:
    """重新索引视频到 TwelveLabs。"""
    # 检查视频是否存在
    video_dir = Path(settings.video_asset_dir)
    video_path = None
    for path in video_dir.rglob("*"):
        if path.is_file() and path.stem == video_id:
            video_path = path
            break

    if video_path is None:
        raise HTTPException(status_code=404, detail="Video not found")

    # TODO: 调用 TwelveLabs API 进行索引
    return {"message": "Video queued for reindexing", "video_id": video_id}


@router.get("/audios", response_model=AudioListResponse)
async def list_audios(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    keyword: Annotated[str | None, Query()] = None,
) -> AudioListResponse:
    """获取音频资产列表。"""
    audios = _scan_audio_dir()

    # 搜索过滤
    if keyword:
        keyword_lower = keyword.lower()
        audios = [a for a in audios if keyword_lower in a.filename.lower()]

    # 分页
    total = len(audios)
    start = (page - 1) * page_size
    end = start + page_size
    page_audios = audios[start:end]

    return AudioListResponse(
        audios=page_audios,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/audios/upload", response_model=UploadResponse)
async def upload_audio(file: UploadFile = File(...)) -> UploadResponse:
    """上传音频文件。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # 检查文件类型
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".mp3", ".wav", ".flac", ".m4a", ".aac"):
        raise HTTPException(status_code=400, detail="Unsupported audio format")

    # 创建目录
    audio_dir = Path(settings.audio_asset_dir)
    audio_dir.mkdir(parents=True, exist_ok=True)

    # 生成唯一文件名（限制文件名长度，避免超过文件系统限制）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(file.filename).stem
    # 文件名最大长度 255 字节，预留 timestamp(15) + suffix(5) + 下划线(1) = 21 字节
    max_stem_len = 100  # 保守限制，避免中文字符占多字节
    if len(stem) > max_stem_len:
        stem = stem[:max_stem_len]
    new_filename = f"{stem}_{timestamp}{suffix}"
    file_path = audio_dir / new_filename

    # 保存文件
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    stat = file_path.stat()

    return UploadResponse(
        id=file_path.stem,
        filename=new_filename,
        path=str(file_path),
        size_bytes=stat.st_size,
    )


@router.delete("/audios/{audio_id}", status_code=204)
async def delete_audio(audio_id: Annotated[str, PathParam()]) -> None:
    """删除音频文件。"""
    audio_dir = Path(settings.audio_asset_dir)

    # 查找匹配的文件
    for path in audio_dir.rglob("*"):
        if path.is_file() and path.stem == audio_id:
            path.unlink()
            return

    raise HTTPException(status_code=404, detail="Audio not found")
