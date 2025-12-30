# Quickstart: TwelveLabs SDK 规范化验证

**Date**: 2025-12-30
**Feature**: 001-twelvelabs-sdk-upgrade

## 快速验证步骤

### 1. 验证异常类型导入

```bash
uv run python -c "
from twelvelabs.exceptions import (
    BadRequestError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    InternalServerError,
)
print('✅ 异常类型导入成功')
"
```

### 2. 验证客户端类型

```bash
uv run python -c "
from twelvelabs import TwelveLabs
client = TwelveLabs(api_key='test')
print(f'✅ 客户端类型: {type(client).__name__}')
"
```

### 3. 运行现有测试

```bash
# 运行 TwelveLabs 相关单元测试
uv run pytest tests/unit/ -k "twelvelabs" -v

# 运行类型检查
uv run mypy src/services/matching/twelvelabs_client.py --ignore-missing-imports
```

### 4. 验证搜索功能（需要有效 API Key）

```bash
# 启动后端服务
uv run python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# 在另一个终端测试搜索
curl -X POST "http://localhost:8000/api/v1/mixes" \
  -H "Content-Type: application/json" \
  -d '{"title": "test", "artist": "test"}'
```

### 5. 验证日志输出

检查日志中是否包含以下事件：
- `twelvelabs.search_query` - 搜索请求
- `twelvelabs.search_success` 或 `twelvelabs.search_failed` - 搜索结果

```bash
# 查看最近日志
tail -f logs/app.log | grep twelvelabs
```

## 验收标准检查清单

- [ ] `from twelvelabs.exceptions import ...` 导入成功
- [ ] `self._client` 类型为 `TwelveLabs | None`
- [ ] 异常处理覆盖 5 种官方异常类型
- [ ] mypy 类型检查通过（无新增错误）
- [ ] 现有搜索功能正常工作
- [ ] 日志包含错误类型信息

## 回滚方案

如果重构导致问题，可以快速回滚：

```bash
# 回滚到 main 分支
git checkout main

# 或回滚特定文件
git checkout main -- src/services/matching/twelvelabs_client.py
```
