from __future__ import annotations

from fastapi import FastAPI

from src.api.v1.routes import mix_lines, mixes, preview, render, render_config
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
