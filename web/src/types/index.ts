// Task types
export interface TaskSummary {
  id: string
  song_title: string
  artist: string | null
  timeline_status: string
  render_status: string
  created_at: string | null
  updated_at: string | null
}

export interface TaskStats {
  total: number
  pending: number
  processing: number
  completed: number
  failed: number
}

export interface TaskListResponse {
  tasks: TaskSummary[]
  stats: TaskStats
  page: number
  page_size: number
  total_pages: number
}

export interface LineDetail {
  id: string
  line_no: number
  original_text: string
  start_time_ms: number
  end_time_ms: number
  status: string
  selected_segment_id: string | null
  candidates_count: number
}

export interface RenderJobSummary {
  id: string
  job_status: string
  progress: number
  submitted_at: string | null
  finished_at: string | null
  error_log: string | null
}

export interface TaskDetail extends TaskSummary {
  source_type: string
  audio_asset_id: string | null
  language: string
  priority: number
  owner_id: string
  error_codes: Record<string, unknown> | null
  metrics: Record<string, unknown> | null
  lines: LineDetail[]
  render_jobs: RenderJobSummary[]
}

// Asset types
export interface VideoAsset {
  id: string
  filename: string
  path: string
  size_bytes: number
  created_at: string
  index_status: string
}

export interface AudioAsset {
  id: string
  filename: string
  path: string
  size_bytes: number
  duration_ms: number | null
  created_at: string
}

export interface VideoListResponse {
  videos: VideoAsset[]
  total: number
  page: number
  page_size: number
}

export interface AudioListResponse {
  audios: AudioAsset[]
  total: number
  page: number
  page_size: number
}

// Config types
export interface RetrieverConfig {
  backend: 'twelvelabs' | 'clip' | 'vlm'
  twelvelabs: Record<string, unknown>
  clip: Record<string, unknown>
  vlm: Record<string, unknown>
}

export interface RenderConfig {
  concurrency_limit: number
  clip_concurrency: number
  per_video_limit: number
  max_retry: number
  retry_backoff_base_ms: number
  metrics_flush_interval_s: number
  placeholder_clip_path: string
}

export interface SystemConfig {
  environment: string
  retriever: RetrieverConfig
  render: RenderConfig
  whisper: {
    model_name: string
    no_speech_threshold: number
  }
  query_rewrite_enabled: boolean
  query_rewrite_mandatory: boolean
}

// System types
export interface SystemStats {
  tasks: TaskStats & { success_rate: number }
  renders: {
    total_jobs: number
    completed: number
    failed: number
    in_progress: number
    average_duration_ms: number | null
  }
  storage: {
    video_count: number
    video_size_bytes: number
    audio_count: number
    audio_size_bytes: number
  }
  uptime_seconds: number
  last_updated: string
}

export interface ServiceHealth {
  name: string
  status: string
  latency_ms: number | null
  error: string | null
}

export interface HealthResponse {
  status: string
  services: ServiceHealth[]
  timestamp: string
}
