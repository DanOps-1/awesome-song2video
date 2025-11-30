from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from src.api.v1.routes import mix_lines, mixes, preview, render, render_config
from src.api.v1.routes.admin import router as admin_router
from src.infra.config.settings import get_settings
from src.infra.observability.otel import configure_logging
from src.infra.persistence.database import init_engine, init_models

# 配置日志（需要在应用启动前）
configure_logging()

app = FastAPI(title="歌词语义混剪 API")
app.include_router(mixes.router)
app.include_router(mix_lines.router)
app.include_router(preview.router)
app.include_router(render.router)
app.include_router(render_config.router)
app.include_router(admin_router)

# 挂载静态文件目录用于视频下载
renders_dir = Path("artifacts/renders")
renders_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/v1/renders", StaticFiles(directory=renders_dir), name="renders")


@app.get("/health")
async def health_check() -> dict[str, str]:
    """供 seed/demo 脚本探活使用。"""
    return {"status": "ok"}


@app.on_event("startup")
async def initialize_infra() -> None:
    """在 API 启动时初始化数据库。"""

    settings = get_settings()
    init_engine(settings.postgres_dsn)
    if settings.environment == "dev":
        await init_models()
