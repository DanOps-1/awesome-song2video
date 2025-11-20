# TwelveLabs Marengo 配置指南

本文档说明如何配置 TwelveLabs Marengo 模型的搜索选项。

## 快速验证

运行以下命令查看当前配置：

```bash
python scripts/dev/verify_config.py
```

## 版本选择

### Marengo 3.0（推荐，默认）

**新特性**：
- ✅ 支持 `transcription` 模态（人声对话转文字）
- ✅ 更长视频支持（4小时 vs 2小时）
- ✅ 36种语言支持（vs 12种）
- ✅ 512维嵌入（性能更好）
- ✅ 更好的体育内容识别
- ✅ 文本+图像组合搜索

**配置**：
```bash
TL_MARENGO_VERSION=3.0
```

### Marengo 2.7（兼容模式）

**限制**：
- ❌ 不支持 `transcription` 模态
- ⚠️ `audio` 包含语音+非语音（无法分离）

**配置**：
```bash
TL_MARENGO_VERSION=2.7
```

## 搜索模态配置

### 1. Visual（视觉）- 始终启用

搜索视觉内容：场景、物体、动作、文字、品牌标志等。

**无需配置，默认启用**

### 2. Audio（音频）- 可选

**Marengo 3.0**：仅搜索非语音音频（音乐、环境声、警报等）
**Marengo 2.7**：搜索所有音频（包含语音+非语音）

```bash
# 启用音频搜索
TL_AUDIO_SEARCH_ENABLED=true

# 禁用音频搜索（默认）
TL_AUDIO_SEARCH_ENABLED=false
```

### 3. Transcription（人声对话）- 可选，仅 Marengo 3.0

搜索视频中的人声对话转文字内容。

```bash
# 启用人声搜索
TL_TRANSCRIPTION_SEARCH_ENABLED=true

# 禁用人声搜索（默认，推荐）
TL_TRANSCRIPTION_SEARCH_ENABLED=false
```

⚠️ **注意**：在 Marengo 2.7 下，即使设置为 `true` 也会被自动忽略。

## Marengo 3.0 高级选项

### Transcription Mode（转录搜索模式）

当启用 `transcription` 时，可选择匹配模式：

```bash
# 语义匹配（默认，推荐）- 理解含义，即使措辞不同
TL_TRANSCRIPTION_MODE=semantic

# 关键词精确匹配 - 适合产品名称、专业术语
TL_TRANSCRIPTION_MODE=lexical

# 两者都用 - 返回最广泛结果
TL_TRANSCRIPTION_MODE=both
```

### Search Operator（多模态组合方式）

当启用多个模态时（如 visual + audio），控制结果组合逻辑：

```bash
# OR - 匹配任意模态（默认）
TL_SEARCH_OPERATOR=or

# AND - 同时匹配所有模态
TL_SEARCH_OPERATOR=and
```

**示例**：
- `["visual", "audio"]` + `or`：视觉**或**音频匹配即返回
- `["visual", "audio"]` + `and`：视觉**和**音频同时匹配才返回

### Confidence Threshold（置信度阈值）

过滤低置信度结果：

```bash
# 不过滤（默认）
TL_CONFIDENCE_THRESHOLD=0.0

# 仅返回置信度 >= 0.5 的结果
TL_CONFIDENCE_THRESHOLD=0.5

# 仅返回高置信度结果
TL_CONFIDENCE_THRESHOLD=0.8
```

范围：`0.0` - `1.0`

## 常见配置场景

### 场景 1：默认配置（推荐）✅

**适用**：大多数视频内容搜索
**特点**：只搜索视觉内容，不包含音频和人声

```bash
TL_MARENGO_VERSION=3.0
TL_AUDIO_SEARCH_ENABLED=false
TL_TRANSCRIPTION_SEARCH_ENABLED=false
```

**搜索选项**：`["visual"]`

---

### 场景 2：视觉 + 背景音乐

**适用**：需要识别背景音乐、环境声的场景
**特点**：搜索视觉和非语音音频（不含人声对话）

```bash
TL_MARENGO_VERSION=3.0
TL_AUDIO_SEARCH_ENABLED=true
TL_TRANSCRIPTION_SEARCH_ENABLED=false
TL_SEARCH_OPERATOR=or
```

**搜索选项**：`["visual", "audio"]`

---

### 场景 3：视觉 + 人声对话（语义匹配）

**适用**：需要搜索视频中对话内容的场景
**特点**：搜索视觉和人声，理解对话含义

```bash
TL_MARENGO_VERSION=3.0
TL_AUDIO_SEARCH_ENABLED=false
TL_TRANSCRIPTION_SEARCH_ENABLED=true
TL_TRANSCRIPTION_MODE=semantic
TL_SEARCH_OPERATOR=or
```

**搜索选项**：`["visual", "transcription"]`
**Transcription Options**：`["semantic"]`

---

### 场景 4：全模态搜索（高精度）

**适用**：需要最全面搜索的场景
**特点**：搜索所有模态，使用高置信度阈值

```bash
TL_MARENGO_VERSION=3.0
TL_AUDIO_SEARCH_ENABLED=true
TL_TRANSCRIPTION_SEARCH_ENABLED=true
TL_TRANSCRIPTION_MODE=both
TL_SEARCH_OPERATOR=or
TL_CONFIDENCE_THRESHOLD=0.6
```

**搜索选项**：`["visual", "audio", "transcription"]`
**Transcription Options**：`["lexical", "semantic"]`
**Confidence**：过滤低于 0.6 的结果

---

### 场景 5：Marengo 2.7 兼容模式

**适用**：使用旧版索引或需要兼容性
**特点**：audio 包含所有音频（语音+非语音）

```bash
TL_MARENGO_VERSION=2.7
TL_AUDIO_SEARCH_ENABLED=true
TL_TRANSCRIPTION_SEARCH_ENABLED=true  # ⚠️ 将被忽略
```

**搜索选项**：`["visual", "audio"]`（transcription 被自动忽略）
**日志警告**：`Marengo 2.7 不支持 transcription 模态，将忽略该选项`

---

## 搜索策略

系统使用**降级策略**确保搜索始终有结果：

1. **第一次尝试**：使用所有启用的模态
2. **失败降级**：自动降级到仅 `visual`

**示例**：
```
配置: ["visual", "audio", "transcription"]
尝试顺序:
  1. ["visual", "audio", "transcription"]  <- 先尝试全部
  2. ["visual"]  <- 失败后降级
```

## 日志监控

搜索时会记录以下日志字段：

```json
{
  "event": "twelvelabs.search_query",
  "query": "a man walking a dog",
  "options": ["visual", "transcription"],
  "marengo_version": "3.0",
  "base_url": "https://api.twelvelabs.io"
}
```

版本兼容性警告：

```json
{
  "event": "twelvelabs.version_incompatible",
  "message": "Marengo 2.7 不支持 transcription 模态，将忽略该选项",
  "version": "2.7"
}
```

## 参考文档

- [Marengo 模型概述](https://docs.twelvelabs.io/v1.3/docs/concepts/models/marengo)
- [搜索选项说明](https://docs.twelvelabs.io/v1.3/docs/concepts/modalities#search-options)
- [搜索 API 文档](https://docs.twelvelabs.io/v1.3/api-reference/any-to-video-search/make-search-request)

## 故障排查

### 问题：搜索结果为空

**检查**：
1. 运行 `python scripts/dev/verify_config.py` 查看配置
2. 检查日志中的 `search_options` 是否正确
3. 尝试降低 `TL_CONFIDENCE_THRESHOLD`
4. 确认索引已正确索引视频内容

### 问题：Transcription 不生效

**检查**：
1. 确认 `TL_MARENGO_VERSION=3.0`（2.7 不支持）
2. 确认 `TL_TRANSCRIPTION_SEARCH_ENABLED=true`
3. 查看日志是否有警告信息
4. 确认索引时启用了 transcription 选项

### 问题：Audio 搜索包含人声

**原因**：Marengo 2.7 的 audio 包含所有音频

**解决**：升级到 Marengo 3.0 并分别启用 `audio` 和 `transcription`
