"""占位片段与临时目录管理辅助函数。"""

from __future__ import annotations

import shutil
from pathlib import Path
import subprocess

import structlog

from src.infra.config.settings import get_settings

logger = structlog.get_logger(__name__)
TMP_ROOT = Path("artifacts/render_tmp")


def ensure_tmp_root() -> Path:
    """确保渲染临时目录存在。"""

    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    return TMP_ROOT


def cleanup_tmp_root() -> None:
    """移除空的临时目录，保持磁盘整洁。"""

    if not TMP_ROOT.exists():
        return
    for child in TMP_ROOT.iterdir():
        if child.is_dir():
            try:
                child.rmdir()
            except OSError:
                # 目录非空，等待 TemporaryDirectory 自行清理
                continue


def ensure_placeholder_asset() -> Path:
    """检查占位片段是否存在。"""

    placeholder = Path(get_settings().placeholder_clip_path)
    if not placeholder.exists():
        msg = f"占位片段不存在: {placeholder}"
        logger.error("placeholder.missing", path=placeholder.as_posix())
        raise FileNotFoundError(msg)
    return placeholder


def copy_placeholder_to(target: Path) -> None:
    """将占位片段复制到目标位置。"""

    placeholder = ensure_placeholder_asset()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(placeholder, target)


def write_placeholder_clip(target: Path, duration_ms: int) -> None:
    """根据目标时长生成占位片段。"""

    placeholder = ensure_placeholder_asset()
    duration = max(duration_ms / 1000.0, 0.5)
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        placeholder.as_posix(),
        "-t",
        f"{duration:.2f}",
        "-c",
        "copy",
        target.as_posix(),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
