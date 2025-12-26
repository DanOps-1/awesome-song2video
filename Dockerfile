# syntax=docker/dockerfile:1

# ==========================================
# 基础镜像 - Python 3.11
# ==========================================
FROM python:3.11-slim AS base

# 防止 Python 生成 .pyc 文件和缓冲输出
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    # FFmpeg 用于视频处理
    ffmpeg \
    # 音频处理依赖
    libsndfile1 \
    # 构建依赖
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ==========================================
# 构建阶段 - 安装依赖
# ==========================================
FROM base AS builder

# 安装 uv 包管理器
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 复制依赖配置
COPY pyproject.toml ./

# 创建虚拟环境并安装依赖
RUN uv venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
RUN uv pip install -e ".[dev]"

# ==========================================
# 运行阶段 - API 服务
# ==========================================
FROM base AS api

# 从构建阶段复制虚拟环境
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# 复制应用代码
COPY src/ ./src/
COPY pyproject.toml ./

# 创建非 root 用户
RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser \
    && chown -R appuser:appgroup /app

USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动 API 服务
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ==========================================
# 运行阶段 - Timeline Worker
# ==========================================
FROM base AS timeline-worker

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY src/ ./src/
COPY pyproject.toml ./

RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser \
    && chown -R appuser:appgroup /app

USER appuser

CMD ["python", "-m", "src.workers.timeline_worker"]

# ==========================================
# 运行阶段 - Render Worker
# ==========================================
FROM base AS render-worker

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY src/ ./src/
COPY pyproject.toml ./

# Render worker 需要写入临时文件
RUN groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser \
    && mkdir -p /app/tmp /app/output \
    && chown -R appuser:appgroup /app

USER appuser

CMD ["python", "-m", "src.workers.render_worker"]
