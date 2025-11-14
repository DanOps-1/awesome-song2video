"""数据库引擎与 Session 管理。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


engine: AsyncEngine | None = None


def init_engine(database_url: str) -> AsyncEngine:
    """基于配置创建全局 AsyncEngine。"""

    global engine  # noqa: PLW0603 - 需要缓存单例
    engine = create_async_engine(database_url, echo=False, future=True)
    return engine


async def init_models() -> None:
    """在启动阶段创建表结构（仅限开发/测试环境）。"""

    if engine is None:
        raise RuntimeError("数据库引擎尚未初始化")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """提供 AsyncSession，上层通过依赖注入或服务层调用。"""

    if engine is None:
        raise RuntimeError("数据库引擎尚未初始化")
    session = AsyncSession(engine, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
