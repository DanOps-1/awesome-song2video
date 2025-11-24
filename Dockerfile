# 使用官方 Python 3.12 基础镜像（基于 Ubuntu）
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖（ffmpeg 等）
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt 并安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建必要的目录
RUN mkdir -p logs artifacts/renders artifacts/render_tmp media/audio media/video

# 暴露端口（如果需要运行 API 服务）
EXPOSE 8000

# 默认命令
CMD ["python", "scripts/dev/run_audio_demo.py"]
