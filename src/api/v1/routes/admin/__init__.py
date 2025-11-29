"""Admin API 路由模块。"""

from fastapi import APIRouter

from . import assets, config, system, tasks

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

router.include_router(tasks.router)
router.include_router(assets.router)
router.include_router(config.router)
router.include_router(system.router)
