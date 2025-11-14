from __future__ import annotations

from fastapi import FastAPI

from src.api.v1.routes import mix_lines, mixes, preview, render


app = FastAPI(title="歌词语义混剪 API")
app.include_router(mixes.router)
app.include_router(mix_lines.router)
app.include_router(preview.router)
app.include_router(render.router)
