# Awesome Song2Video Constitution

## Core Principles

### I. Documentation First

所有功能开发 MUST 遵循文档驱动流程：先完成规格说明（spec）和设计文档，经审批后再进行编码实现。

- 新功能 MUST 先创建 `.specify/features/<feature>/spec.md`
- 设计决策 MUST 记录在 `plan.md` 中，包含替代方案分析
- API 变更 MUST 先更新接口文档（FastAPI 自动生成 OpenAPI）
- 代码注释用于解释"为什么"，文档用于解释"是什么"和"如何使用"

**理由**: 文档驱动确保开发前充分思考，减少返工，提高团队协作效率。

### II. Async-First Architecture

本项目是异步优先的后端系统，所有 I/O 操作 MUST 使用异步模式。

- 数据库操作 MUST 使用 async SQLAlchemy + SQLModel
- 外部 API 调用 MUST 使用 httpx async client
- 文件 I/O SHOULD 使用 aiofiles
- Worker 任务 MUST 通过 ARQ + Redis 异步队列处理
- 禁止在异步上下文中使用阻塞调用（如 `time.sleep`、同步 `requests`）

**理由**: 视频处理和 AI 推理是 I/O 密集型任务，异步架构最大化吞吐量。

### III. Code Quality

代码质量是不可妥协的基本要求。所有代码 MUST 遵循以下标准：

- Python 代码 MUST 通过 Ruff lint 和 format 检查
- 类型提示 MUST 完整，通过 mypy 严格模式检查
- 函数/方法 SHOULD 保持单一职责，不超过 50 行
- 禁止使用 `Any` 类型，除非有充分理由并添加注释说明
- 前端 TypeScript MUST 启用严格模式（`strict: true`）

**理由**: 高质量代码降低维护成本，提高系统可靠性。

### IV. Security First

安全 MUST 作为设计和开发的首要考虑因素，而非事后补救。

- 用户输入 MUST 进行验证（Pydantic 模型自动验证）
- API 密钥（TwelveLabs、DeepSeek 等）MUST 通过环境变量配置，禁止硬编码
- 敏感数据禁止明文日志记录
- 文件上传 MUST 验证类型和大小限制
- 依赖项 SHOULD 定期扫描安全漏洞

**理由**: 安全漏洞的修复成本随时间呈指数增长，预防远优于补救。

### V. Data Authenticity

数据真实性是系统可信度的基础。MUST 确保数据的准确性和可追溯性。

- 禁止在生产环境使用模拟或伪造数据
- 歌词数据 MUST 来自真实来源（QQ音乐/网易云/酷狗/LRCLIB 或 Whisper ASR）
- 视频匹配结果 MUST 反映 TwelveLabs API 真实返回，禁止"美化"分数
- 渲染进度 MUST 反映真实状态，禁止虚假进度条

**理由**: 用户决策依赖真实数据，虚假数据会导致错误决策和信任丧失。

### VI. Simplicity

简洁性是对抗复杂度的核心武器。MUST 遵循 YAGNI（You Aren't Gonna Need It）原则。

- 只实现当前需求明确要求的功能
- 避免"以防万一"的抽象和配置
- 三次重复再考虑抽象（Rule of Three）
- 优先选择组合而非继承
- 删除未使用的代码，而非注释掉

**理由**: 过度工程增加维护负担，降低开发速度，引入不必要的 bug。

### VII. Observability

系统 MUST 具备完整的可观测性，确保问题可被快速发现和定位。

- 所有服务 MUST 使用 structlog 输出结构化日志
- 日志事件名 MUST 遵循 `module.action` 格式（如 `timeline.match_started`）
- 关键业务操作 MUST 记录日志，包含 mix_id 用于追踪
- Worker 任务 MUST 记录开始、完成、失败状态
- 错误 MUST 包含足够的上下文信息（歌词行号、视频 ID 等）

**理由**: 没有可观测性的系统是"黑盒"，问题排查将极其困难。

### VIII. Test Coverage

测试是代码质量的保障。MUST 达到并维持测试覆盖率标准。

- 新代码 SHOULD 有对应的单元测试
- 关键业务逻辑（TimelineBuilder、RenderWorker）MUST 有测试覆盖
- 修复 Bug 时 SHOULD 先添加复现该 Bug 的测试
- 测试 MUST 是确定性的，禁止随机失败
- 异步测试 MUST 使用 pytest-asyncio

**理由**: 充分的测试覆盖提供重构信心，防止回归问题。

## Technical Constraints

本项目采用以下技术栈和约束：

### 语言规范

- 所有文档 MUST 使用中文撰写（spec.md, plan.md, tasks.md, README 等）
- 代码注释 SHOULD 使用中文
- Git 提交信息 SHOULD 使用中文
- 变量名、函数名、类名 MUST 使用英文

---

### Python 后端规范

**Python 版本与环境**
- Python 版本 MUST ≥ 3.11
- 包管理 MUST 使用 uv，禁止使用 pip/poetry/pipenv
- 所有 Python 命令 MUST 使用 `uv run` 前缀运行
- 项目配置 MUST 统一使用 `pyproject.toml`
- `uv.lock` MUST 提交到 Git，确保依赖版本一致性
- 项目结构 MUST 使用 `src/` 布局

**类型提示（现代语法）**
- MUST 使用 PEP 585 语法：`list[str]`, `dict[str, int]`（禁止 `typing.List`, `typing.Dict`）
- MUST 使用 PEP 604 语法：`int | None`（禁止 `Optional[int]`, `Union[X, Y]`）
- 类型检查 MUST 使用 mypy，严格模式启用
- 禁止使用 `Any` 类型，除非有充分理由并添加注释

**代码质量工具**
- Linter/Formatter MUST 使用 Ruff
- 行长度限制：100 字符
- 提交前 MUST 运行：`uv run ruff check src tests && uv run ruff format --check src tests`

**数据模型**
- API 输入/输出 MUST 使用 Pydantic v2 模型
- 数据库模型 MUST 使用 SQLModel
- 配置管理 MUST 使用 pydantic-settings（`src/infra/config/settings.py`）

**现代语法强制**
- 文件路径 MUST 使用 `pathlib.Path`（禁止 `os.path`）
- 字符串格式化 MUST 使用 f-string（禁止 `%` 和 `.format()`）
- 异步 I/O MUST 优先使用 `async/await`
- 上下文管理 MUST 使用 `with` 语句
- 异常处理 MUST 指定具体异常类型（禁止裸 `except:`）

**框架与库**
- API 框架：FastAPI（自动 OpenAPI 文档、类型验证）
- 数据库：async SQLAlchemy 2.0 + SQLModel + asyncpg
- 结构化日志：structlog
- 异步队列：ARQ + Redis
- 视频处理：FFmpeg（通过 python-ffmpeg）
- AI/ML：Whisper（语音识别）、TwelveLabs（视频搜索）、DeepSeek（查询改写）

**测试**
- 测试框架 MUST 使用 pytest
- 异步测试 MUST 使用 pytest-asyncio（`asyncio_mode = "auto"`）
- 测试目录结构：`tests/unit/`、`tests/integration/`、`tests/contract/`

---

### TypeScript 前端规范

**前端应用**
- 用户前端：`apps/frontend`（端口 6008）
- 管理后台：`apps/web`（端口 6006）

**技术栈**
- Node.js ≥ 18
- 构建工具：Vite
- 包管理器：npm
- TypeScript 严格模式（`strict: true`）

**代码质量**
- 提交前 MUST 运行构建检查：`npx vite build`
- 禁止使用 `any` 类型

---

### 通用规范

- Git 分支策略：主干开发（main 分支）
- CI/CD MUST 包含：lint, format-check, typecheck, test, build
- 依赖安全扫描 SHOULD 定期执行

## Development Workflow

开发工作流遵循以下步骤：

1. **需求澄清**：在 `.specify/features/<feature>/` 创建 `spec.md`
2. **设计规划**：完成 `plan.md`，明确技术方案
3. **任务拆分**：生成 `tasks.md`，分解为可执行任务
4. **实现开发**：按任务顺序实现，每个任务独立提交
5. **测试验证**：确保测试通过，运行 `uv run pytest tests/`
6. **代码检查**：运行完整的 pre-commit 检查
7. **代码提交**：CI 检查通过后可合并

**Pre-commit 检查清单**：
```bash
# 1. Python 代码检查（必须通过）
uv run ruff check src tests && uv run ruff format --check src tests

# 2. 前端构建检查（必须通过）
cd apps/frontend && npx vite build

# 3. 管理后台构建检查（必须通过）
cd apps/web && npx vite build
```

**合并要求**：
- 所有 CI 检查 MUST 通过（lint, build）
- 提交信息 SHOULD 遵循 Conventional Commits 规范

## Architecture Overview

### 核心数据流
1. **音频上传** → 用户上传音频文件
2. **歌词获取** → 多源在线搜索（QQ/网易云/酷狗/LRCLIB）或 Whisper ASR
3. **歌词确认** → 用户审核/编辑歌词
4. **视频匹配** → TwelveLabs API 为每行歌词匹配视频片段
5. **渲染输出** → FFmpeg 拼接视频片段 + 音频 + 字幕

### 关键服务
- **LyricsFetcher** (`src/lyrics/fetcher.py`)：多源歌词获取
- **TimelineBuilder** (`src/pipelines/matching/timeline_builder.py`)：编排转录和视频搜索
- **QueryRewriter** (`src/services/matching/query_rewriter.py`)：LLM 查询改写
- **RenderWorker** (`src/workers/render_worker.py`)：并行视频渲染
- **BeatAligner** (`src/services/matching/beat_aligner.py`)：节拍卡点对齐

### 数据库模型
- `SongMixRequest`：混剪请求主实体
- `LyricLine`：歌词行（含时间戳）
- `VideoSegmentMatch`：视频候选片段
- `RenderJob`：渲染任务追踪
- `BeatAnalysisData`：节拍分析结果

## Governance

本 Constitution 是项目开发的最高指导原则。

**优先级**：Constitution > 技术文档 > 代码注释 > 口头约定

**修订流程**：
1. 提出修订 PR，包含变更说明和影响分析
2. 记录版本变更和修订日期
3. 同步更新受影响的模板和文档

**版本规则**（语义化版本）：
- MAJOR：原则删除或根本性重新定义
- MINOR：新增原则或实质性扩展
- PATCH：措辞澄清、格式修正

**合规检查**：
- 每次代码审查 SHOULD 验证是否符合 Constitution 原则
- 发现违反原则的代码 MUST 记录并在合理时间内修复

**Version**: 1.0.0 | **Ratified**: 2025-12-30 | **Last Amended**: 2025-12-30
