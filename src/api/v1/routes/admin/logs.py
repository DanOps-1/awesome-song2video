"""日志查看 API - 开发者后台实时日志。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/logs", tags=["admin-logs"])

LOG_DIR = Path("logs")
DEFAULT_LOG_FILE = "app.log"


class LogEntry(BaseModel):
    """日志条目。"""

    timestamp: str | None = None
    level: str | None = None
    event: str | None = None
    raw: str


class LogQueryResponse(BaseModel):
    """日志查询响应。"""

    lines: list[LogEntry]
    total: int
    file: str


def parse_log_line(line: str) -> LogEntry:
    """解析日志行（支持 JSON 和纯文本格式）。"""
    line = line.strip()
    if not line:
        return LogEntry(raw="")

    # 尝试解析 JSON 格式
    if line.startswith("{"):
        try:
            data = json.loads(line)
            return LogEntry(
                timestamp=data.get("timestamp"),
                level=data.get("level"),
                event=data.get("event"),
                raw=line,
            )
        except json.JSONDecodeError:
            pass

    # 纯文本格式
    return LogEntry(raw=line)


@router.get("", response_model=LogQueryResponse)
async def get_logs(
    file: str = Query(DEFAULT_LOG_FILE, description="日志文件名"),
    lines: int = Query(100, ge=1, le=1000, description="返回行数"),
    filter: str | None = Query(None, description="过滤关键词（如 beat, render）"),
    level: str | None = Query(None, description="日志级别过滤（info, warning, error）"),
) -> LogQueryResponse:
    """获取最近的日志。

    支持按关键词和级别过滤。
    """
    log_path = LOG_DIR / file
    if not log_path.exists():
        return LogQueryResponse(lines=[], total=0, file=file)

    # 读取文件末尾
    all_lines: list[str] = []
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        all_lines = f.readlines()

    # 从后往前过滤
    result: list[LogEntry] = []
    for raw_line in reversed(all_lines):
        if len(result) >= lines:
            break

        raw_line = raw_line.strip()
        if not raw_line:
            continue

        # 关键词过滤
        if filter and filter.lower() not in raw_line.lower():
            continue

        entry = parse_log_line(raw_line)

        # 级别过滤
        if level and entry.level and entry.level.lower() != level.lower():
            continue

        result.append(entry)

    # 反转回正序
    result.reverse()

    return LogQueryResponse(lines=result, total=len(result), file=file)


@router.get("/stream")
async def stream_logs(
    file: str = Query(DEFAULT_LOG_FILE, description="日志文件名"),
    filter: str | None = Query(None, description="过滤关键词"),
) -> StreamingResponse:
    """实时日志流（Server-Sent Events）。

    前端使用 EventSource 连接：
    ```javascript
    const es = new EventSource('/api/v1/admin/logs/stream?filter=beat');
    es.onmessage = (e) => console.log(JSON.parse(e.data));
    ```
    """

    async def generate() -> AsyncGenerator[str, None]:
        log_path = LOG_DIR / file
        if not log_path.exists():
            yield f"data: {json.dumps({'error': 'log file not found'})}\n\n"
            return

        # 从文件末尾开始
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            # 移动到文件末尾
            f.seek(0, 2)

            while True:
                line = f.readline()
                if line:
                    line = line.strip()
                    if line:
                        # 关键词过滤
                        if filter and filter.lower() not in line.lower():
                            continue

                        entry = parse_log_line(line)
                        yield f"data: {json.dumps(entry.model_dump())}\n\n"
                else:
                    # 没有新数据，等待
                    await asyncio.sleep(0.5)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )


@router.get("/files")
async def list_log_files() -> dict[str, list[dict]]:
    """列出可用的日志文件。"""
    files = []
    if LOG_DIR.exists():
        for f in LOG_DIR.iterdir():
            if f.is_file() and f.suffix in (".log", ".log.1", ".log.2"):
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": int(f.stat().st_mtime),
                })

    # 按修改时间倒序
    files.sort(key=lambda x: x["modified"], reverse=True)
    return {"files": files}
