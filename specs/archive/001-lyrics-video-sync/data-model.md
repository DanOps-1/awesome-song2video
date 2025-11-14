# 数据模型：歌词语义混剪视频

## SongMixRequest

- **描述**：一次完整的混剪任务，涵盖歌词解析、语义匹配、人工校对与渲染导出。
- **核心字段**：
  - `id (UUID)`：主键。
  - `song_title (str)`：歌曲名称，必填，<=128 字符。
  - `artist (str)`：可选，<=128 字符。
  - `source_type (enum: upload|catalog)`：上传音频 or 歌曲库引用。
  - `audio_asset_id (str)`：对象存储引用，上传必填。
  - `lyrics_text (text)`：原始歌词，UTF-8。
  - `language (enum: zh|en|mix|other)`：用于选择识别模型。
  - `timeline_status (enum: pending|generated|in_review|approved)`。
  - `render_status (enum: idle|queued|processing|done|failed)`。
  - `priority (int)`：渲染优先级，默认 5，范围 1-9。
  - `owner_id (UUID)`：提交人。
  - `created_at/updated_at (datetime, tz)`。
  - `error_codes (jsonb)`：阶段性错误。
  - `metrics (jsonb)`：记录生成耗时、匹配命中率等。
- **校验/规则**：
  - `lyrics_text` 与 `audio_asset_id` 至少提供其一。
  - 若 `render_status=done`，必须存在 `output_asset_id`。
  - `priority` 与排队策略绑定，越小优先级越高。
- **状态迁移**：
  - `pending → generated`（歌词解析完成）。
  - `generated → in_review`（自动生成完成并推送审核）。
  - `in_review → approved`（人工确认）。
  - `approved → render_status.queued`（提交渲染）。
  - 渲染完成/失败分别进入 `done/failed`。

## LyricLine

- **描述**：歌曲中的单句歌词，附带时间范围与选定视频片段。
- **核心字段**：
  - `id (UUID)`，`mix_request_id (UUID)`。
  - `line_no (int)`：从 1 开始。
  - `original_text (str)`、`translated_text (str|null)`。
  - `start_time_ms / end_time_ms (int)`：以毫秒计。
  - `auto_confidence (float)`：0-1，来自 TwelveLabs。
  - `selected_segment_id (UUID|null)`：关联 VideoSegmentMatch。
  - `status (enum: pending|auto_selected|edited|locked)`。
  - `annotations (text)`：人工备注。
  - `audit_log (jsonb)`：记录替换历史。
- **校验/规则**：
  - `start_time_ms < end_time_ms`，间隔 ≥ 500ms。
  - `line_no` 在同一请求内唯一。
  - `status=locked` 时禁止再编辑。
- **状态迁移**：`pending → auto_selected → edited/locked`。人工校对后设置 locked。

## VideoSegmentMatch

- **描述**：TwelveLabs 返回的候选视频片段，可作为时间线素材。
- **核心字段**：
  - `id (UUID)`。
  - `line_id (UUID)`：所属 LyricLine。
  - `source_video_id (str)`：媒资库唯一标识。
  - `index_id (str)`：本项目固定 `6911aaadd68fb776bc1bd8e7`。
  - `start_time_ms / end_time_ms (int)`：片段相对原视频起止。
  - `score (float)`：SDK 评分。
  - `tags (jsonb)`：TwelveLabs 返回的主题标签。
  - `preview_url (str)`：供前端预览。
  - `generated_by (enum: auto|rerank|manual)`：产生方式。
  - `created_at (datetime)`。
- **校验/规则**：
  - 同一 `line_id` 下最多保留 10 条候选。
  - `end_time_ms - start_time_ms` 需覆盖歌词持续时间 ±1s。

## RenderJob

- **描述**：渲染队列任务，消费已锁定的时间线并输出视频。
- **核心字段**：
  - `id (UUID)`，`mix_request_id (UUID)`。
  - `job_status (enum: queued|running|success|failed|canceled)`。
  - `worker_node (str)`：执行节点。
  - `ffmpeg_script (text)`：生成的 filtergraph。
  - `progress (float)`：0-1。
  - `output_asset_id (str|null)`。
  - `error_log (text)`。
  - `submitted_at / finished_at (datetime)`。
- **关系**：1:1 对应 SongMixRequest（approved 后创建），但允许重试生成新 job（历史保留）。

## Entity 关系概览

- `SongMixRequest 1 - n LyricLine`。
- `LyricLine 1 - n VideoSegmentMatch`。
- `SongMixRequest 1 - n RenderJob`（重试时多条）。
- `RenderJob` 读取 `LyricLine` 的 `selected_segment_id` 生成脚本。

## 业务约束

- 删除 SongMixRequest 时级联软删除相关 LyricLine/VideoSegmentMatch（保留审计）。
- LyricLine 在 `status=locked` 后才能发起 RenderJob。
- RenderJob 的 `success` 必须写回 `SongMixRequest.render_status=done` 并记录输出资产。
