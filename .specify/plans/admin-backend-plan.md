# 开发者 Web 后台实现计划

## 概述

基于现有 FastAPI 后端扩展管理 API，并创建 React + Tailwind 前端界面。

## 现有 API 分析

### 已有端点
- `POST /api/v1/mixes` - 创建混剪任务
- `POST /api/v1/mixes/{mix_id}/generate-timeline` - 生成时间线
- `GET /api/v1/mixes/{mix_id}/lines` - 获取歌词行列表
- `PATCH /api/v1/mixes/{mix_id}/lines/{line_id}` - 更新歌词行
- `POST /api/v1/mixes/{mix_id}/render` - 提交渲染
- `GET /api/v1/mixes/{mix_id}/render` - 获取渲染状态
- `GET/PATCH /render/config` - 渲染配置

### 数据模型
- **SongMixRequest**: 混剪任务（含状态、指标）
- **LyricLine**: 歌词行（含候选片段）
- **VideoSegmentMatch**: 视频片段匹配
- **RenderJob**: 渲染任务

---

## 新增管理 API 设计

### 1. 任务管理 API (`/api/v1/admin/tasks`)

```
GET  /api/v1/admin/tasks
     - 分页列表
     - 筛选: status, date_range, keyword
     - 返回: 任务列表 + 统计

GET  /api/v1/admin/tasks/{task_id}
     - 任务详情
     - 包含: lines, render_jobs, metrics

POST /api/v1/admin/tasks/{task_id}/retry
     - 重试失败任务

DELETE /api/v1/admin/tasks/{task_id}
     - 删除任务

GET  /api/v1/admin/tasks/{task_id}/logs
     - 获取任务日志
```

### 2. 素材管理 API (`/api/v1/admin/assets`)

```
GET  /api/v1/admin/assets/videos
     - 视频库列表
     - 分页 + 搜索

POST /api/v1/admin/assets/videos/upload
     - 上传视频

DELETE /api/v1/admin/assets/videos/{video_id}
     - 删除视频

GET  /api/v1/admin/assets/videos/{video_id}/index-status
     - TwelveLabs 索引状态

POST /api/v1/admin/assets/videos/{video_id}/reindex
     - 重新索引

GET  /api/v1/admin/assets/audios
     - 音频库列表

POST /api/v1/admin/assets/audios/upload
     - 上传音频
```

### 3. 配置管理 API (`/api/v1/admin/config`)

```
GET  /api/v1/admin/config
     - 获取所有可配置项

PATCH /api/v1/admin/config
     - 更新配置

GET  /api/v1/admin/config/retriever
     - 检索后端状态

POST /api/v1/admin/config/retriever/switch
     - 切换检索后端
```

### 4. 系统监控 API (`/api/v1/admin/system`)

```
GET  /api/v1/admin/system/stats
     - 系统统计（任务数、成功率等）

GET  /api/v1/admin/system/health
     - 服务健康状态
```

---

## 前端架构设计

### 技术栈
- **React 18** + TypeScript
- **Tailwind CSS** + shadcn/ui 组件库
- **React Router** 路由
- **TanStack Query** 数据获取
- **Zustand** 状态管理

### 项目结构

```
web/
├── package.json
├── tailwind.config.js
├── vite.config.ts
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── api/                    # API 客户端
    │   ├── client.ts
    │   ├── tasks.ts
    │   ├── assets.ts
    │   └── config.ts
    ├── components/             # 通用组件
    │   ├── ui/                 # shadcn/ui 组件
    │   ├── Layout.tsx
    │   ├── Sidebar.tsx
    │   └── Header.tsx
    ├── pages/                  # 页面组件
    │   ├── Dashboard.tsx       # 仪表盘
    │   ├── tasks/
    │   │   ├── TaskList.tsx
    │   │   └── TaskDetail.tsx
    │   ├── assets/
    │   │   ├── VideoLibrary.tsx
    │   │   └── AudioLibrary.tsx
    │   └── settings/
    │       ├── GeneralConfig.tsx
    │       └── RetrieverConfig.tsx
    ├── hooks/                  # 自定义 hooks
    ├── stores/                 # Zustand stores
    └── types/                  # TypeScript 类型
```

### 页面设计

#### 1. 仪表盘 (Dashboard)
- 任务统计卡片（总数、进行中、成功、失败）
- 最近任务列表
- 渲染成功率图表
- 系统状态

#### 2. 任务管理 (Tasks)
- 任务列表（分页、筛选、搜索）
- 任务详情弹窗
  - 基本信息
  - 歌词行列表
  - 候选片段预览
  - 渲染日志
- 操作按钮（重试、删除）

#### 3. 素材库 (Assets)
- 视频库标签页
  - 视频网格/列表视图
  - 上传按钮
  - 索引状态标签
- 音频库标签页
  - 音频列表
  - 上传/播放

#### 4. 配置管理 (Settings)
- 检索后端切换
- 渲染配置表单
- TwelveLabs 设置
- 模型配置

---

## 实现步骤

### Phase 1: 后端 Admin API
1. 创建 `src/api/v1/routes/admin/` 目录
2. 实现任务管理 API
3. 实现素材管理 API
4. 实现配置管理 API
5. 实现系统监控 API

### Phase 2: 前端项目初始化
1. 创建 `web/` 目录
2. 初始化 Vite + React + TypeScript
3. 配置 Tailwind CSS
4. 安装 shadcn/ui 组件
5. 设置路由和布局

### Phase 3: 核心页面开发
1. 实现 Layout 和导航
2. 实现 Dashboard 页面
3. 实现任务列表和详情
4. 实现素材库页面
5. 实现配置管理页面

### Phase 4: 集成和优化
1. API 客户端封装
2. 错误处理
3. 加载状态
4. 响应式适配

---

## 文件清单

### 后端新增文件
```
src/api/v1/routes/admin/
├── __init__.py
├── tasks.py          # 任务管理 API
├── assets.py         # 素材管理 API
├── config.py         # 配置管理 API
└── system.py         # 系统监控 API
```

### 前端新增文件
```
web/
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── index.css
    ├── api/
    ├── components/
    ├── pages/
    ├── hooks/
    ├── stores/
    └── types/
```
