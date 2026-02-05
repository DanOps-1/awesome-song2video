# Docker 使用指南

## 1. 安装 Docker Desktop

### macOS 安装步骤：

1. **下载 Docker Desktop**
   - 访问：https://www.docker.com/products/docker-desktop/
   - 点击 "Download for Mac"
   - 根据你的 Mac 芯片选择：
     - Apple Silicon (M1/M2/M3): ARM 版本
     - Intel 芯片: Intel 版本

2. **安装**
   - 打开下载的 `.dmg` 文件
   - 拖动 Docker 图标到 Applications 文件夹
   - 打开 Docker Desktop
   - 等待 Docker 启动（状态栏会显示 Docker 图标）

3. **验证安装**
   ```bash
   docker --version
   docker-compose --version
   ```

---

## 2. 使用 Docker 运行项目（不修改任何源码）

### 方式 A：使用 docker-compose（推荐，最简单）

```bash
# 1. 构建并运行
docker-compose up --build

# 2. 如果要在后台运行
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 停止
docker-compose down
```

### 方式 B：使用 docker 命令

```bash
# 1. 构建镜像
docker build -t twelve_labs .

# 2. 运行容器
docker run --rm \
  -v $(pwd):/app \
  twelve_labs

# 3. 如果需要交互式运行
docker run -it --rm \
  -v $(pwd):/app \
  twelve_labs bash
```

---

## 3. 常用操作

### 运行不同的脚本

```bash
# 运行 demo
docker-compose run --rm twelve_labs python scripts/dev/run_audio_demo.py

# 运行测试
docker-compose run --rm twelve_labs pytest

# 进入容器 shell
docker-compose run --rm twelve_labs bash
```

### 清理

```bash
# 停止并删除容器
docker-compose down

# 删除镜像
docker rmi twelve_labs

# 清理所有未使用的资源
docker system prune -a
```

---

## 4. 优势

✅ **不修改任何源码** - 仓库代码保持原样
✅ **环境隔离** - 不会影响你的 Mac 环境
✅ **和服务器一致** - 都是 Linux 环境
✅ **避免 macOS 兼容性问题** - 所有依赖在容器内运行

---

## 5. 常见问题

### Q: 为什么第一次运行很慢？
A: Docker 需要：
   - 下载基础镜像（约 200MB）
   - 安装所有依赖

   之后会很快，因为都缓存了。

### Q: 如何修改代码？
A: 直接在 Mac 上编辑代码文件，Docker 会自动同步（通过 volume 挂载）。

---

## 6. 下一步

安装完 Docker Desktop 后，在项目根目录运行：

```bash
docker-compose up --build
```

就可以看到程序在 Linux 容器中运行，不会有任何崩溃问题！
