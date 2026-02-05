# 使用轻量级 Python 镜像（已移除 Whisper，无需 GPU）
FROM python:3.11-slim-bookworm

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# 安装系统依赖（FFmpeg 用于视频处理）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN pip install --no-cache-dir uv

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 安装依赖（不安装项目本身，只安装依赖）
RUN uv sync --frozen --no-install-project

# 复制项目代码
COPY . .

# 安装项目本身
RUN uv sync --frozen

# 创建必要的目录
RUN mkdir -p logs artifacts/renders artifacts/render_tmp media/audio media/video media/fallback

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 默认命令：启动 API 服务
CMD ["uv", "run", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
