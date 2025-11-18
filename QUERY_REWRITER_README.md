# 查询改写功能 (Query Rewriter)

## 功能说明

查询改写功能通过 AI 将抽象、隐喻、情感化的歌词转换为具体的视觉描述，以提高视频搜索的匹配率。

**🆕 智能重试机制**：如果改写后仍无匹配，系统会自动使用不同策略重新改写，直到成功或达到最大尝试次数。

## 工作原理

### 智能重试降级策略

系统采用多级智能重试策略（默认最多3次尝试）：

1. **原始查询** → 有候选 → 使用
2. **原始查询** → 无候选 → **AI改写（第1次：具体视觉描述）** → 重试
3. **仍无候选** → **AI改写（第2次：通用情感场景）** → 重试
4. **仍无候选** → **AI改写（第3次：极简关键词）** → 重试
5. **仍无候选** → 返回空（使用fallback视频）

### 改写策略演进

每次重试使用不同的改写策略，逐步降级到更通用的描述：

| 尝试次数 | 策略 | 温度参数 | 说明 |
|---------|------|---------|------|
| 第1次 | 具体视觉描述 | 0.3 | 转换为详细的视觉元素（人物、动作、场景、表情） |
| 第2次 | 通用情感场景 | 0.5 | 去专业化，聚焦情感状态和日常动作 |
| 第3次 | 极简关键词 | 0.7 | 只保留3-5个核心关键词 |
| 第4次+ | 最简抽象 | 1.0 | 使用最简单最通用的2-3个单词 |

### 改写示例

#### 单次改写成功

| 原始歌词（抽象） | 改写后（具体视觉描述） | 结果 |
|--------------|------------------|------|
| I can't lose nothing twice | sad person, defeated expression, sitting alone, dark room, looking down, empty hands | ✅ 3个候选 |
| But I'm standing with the weight | person struggling, heavy burden, tired face, stressful situation, carrying weight | ✅ 2个候选 |
| 我的心像海 | calm ocean, vast water, peaceful scene, blue waves, serene mood | ✅ 匹配 |

#### 智能重试成功案例

**示例1：士兵场景 → 通用化**

| 尝试 | 改写结果 | 匹配数 |
|------|---------|--------|
| 第1次（具体） | soldier in pain, battlefield scene, wounded expression, military uniform | ❌ 0个 |
| 第2次（通用） | person in pain, struggling, worried expression, difficult situation | ✅ 3个 |

**示例2：金钱场景 → 情感化**

| 尝试 | 改写结果 | 匹配数 |
|------|---------|--------|
| 第1次（具体） | person paying bills, calendar showing first day, money exchange, stressed expression | ❌ 0个 |
| 第2次（通用） | stressed person, worried face, paperwork, tense moment | ✅ 2个 |
| ~~第3次~~ | ~~（已成功，跳过）~~ | - |

**示例3：极简降级**

| 尝试 | 改写结果 | 匹配数 |
|------|---------|--------|
| 第1次（具体） | praying hands, spiritual atmosphere, peaceful expression, closed eyes | ❌ 0个 |
| 第2次（通用） | person sitting quietly, peaceful expression, closed eyes, calm atmosphere | ❌ 0个 |
| 第3次（极简） | peaceful person, calm, quiet | ✅ 1个 |

## 配置

### 1. 安装依赖

```bash
pip install openai>=1.0.0
```

### 2. 环境变量配置

在 `.env` 文件中添加以下配置：

```env
# DeepSeek API 密钥（必需）
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# DeepSeek API 地址（可选，默认 https://api.deepseek.com/v1）
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# 是否启用查询改写（可选，默认 true）
QUERY_REWRITE_ENABLED=true
```

### 3. 获取 DeepSeek API Key

1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com/)
2. 注册/登录账号
3. 创建 API Key
4. 复制 Key 到 `.env` 文件

## 使用方式

### 自动使用

配置完成后，系统会自动在以下场景使用查询改写：

- 调用 `/api/v1/songs` 创建歌曲时
- 调用 `/api/v1/mixes` 创建混剪时
- 后台 timeline 构建过程中

### 手动测试

运行测试脚本验证功能：

```bash
python test_query_rewriter.py
```

### 编程使用

```python
from src.services.matching.query_rewriter import QueryRewriter

# 初始化
rewriter = QueryRewriter()

# 改写查询
rewritten = await rewriter.rewrite("I can't lose nothing twice")
# 输出: "sad person, defeated expression, sitting alone, dark room..."
```

## 日志监控

系统会输出详细的日志帮助你监控改写效果：

```log
# 改写触发
[info] timeline_builder.fallback_to_rewrite original="I can't lose nothing twice"

# 改写结果
[info] timeline_builder.rewrite_result
  original="I can't lose nothing twice"
  rewritten="sad person, defeated expression..."
  count=5

# 最终候选
[info] timeline_builder.candidates
  text_preview="I can't lose nothing twice"
  count=5
  use_mock=False
```

## 性能优化

### 缓存机制

- 改写结果会被缓存在内存中
- 相同的原始查询只会调用一次 API
- 缓存在 `TimelineBuilder` 实例生命周期内有效

### 成本控制

- 使用 DeepSeek API（成本低廉）
- 仅在无候选时触发改写
- 改写请求设置了 `temperature=0.3` 和 `max_tokens=100`

## 故障排查

### 问题：改写没有生效

**检查清单：**

1. 确认 `DEEPSEEK_API_KEY` 已配置且有效
2. 确认 `QUERY_REWRITE_ENABLED=true`
3. 检查日志是否有 `query_rewriter.initialized enabled=True`
4. 检查是否有网络连接问题

### 问题：改写结果不理想

**解决方案：**

1. **修改 system prompt**：编辑 `src/services/matching/query_rewriter.py:81-107`
2. **调整温度参数**：修改 `temperature` 值（当前 0.3）
3. **切换模型**：将 `deepseek-chat` 换为其他模型

### 问题：API 调用失败

**日志示例：**

```log
[warning] query_rewriter.failed original="..." error="..."
```

**解决方案：**

- 系统会自动降级到原始查询，不会影响整体流程
- 检查 API Key 是否过期
- 检查网络连接和 API 端点可用性

## 高级配置

### 使用其他 LLM 服务

修改 `src/services/matching/query_rewriter.py` 中的 `base_url` 和模型名称：

```python
# 使用 OpenAI
DEEPSEEK_BASE_URL=https://api.openai.com/v1
# 在代码中修改 model="gpt-4"

# 使用本地 Ollama
DEEPSEEK_BASE_URL=http://localhost:11434/v1
# 在代码中修改 model="llama2"
```

### 禁用改写

```env
QUERY_REWRITE_ENABLED=false
```

或不配置 `DEEPSEEK_API_KEY`，系统会自动禁用。

## 更新记录

- **2025-11-18**: 初始版本发布
  - 支持 DeepSeek API
  - 智能降级策略
  - 缓存优化
  - 完整日志监控

## 相关文件

- `src/services/matching/query_rewriter.py` - 核心改写逻辑
- `src/pipelines/matching/timeline_builder.py` - 集成降级策略
- `src/infra/config/settings.py` - 配置定义
- `test_query_rewriter.py` - 测试脚本
