import apiClient from './client'

export interface CreateMixRequest {
  song_title: string
  artist?: string
  audio_file?: File
  lyrics_text?: string
  language?: string
}

export interface MixResponse {
  id: string
  song_title: string
  timeline_status: string
  timeline_progress: number
  lyrics_confirmed: boolean
  render_status: string
  lines: LineInfo[]
}

export interface LineInfo {
  id: string
  line_no: number
  original_text: string
  start_time_ms: number
  end_time_ms: number
  status: string
  candidates: Array<{
    id: string
    preview_url?: string
    score: number
  }>
}

export interface PreviewManifest {
  manifest: Array<{
    line_id: string
    text: string
    video_url?: string
    fallback: boolean
  }>
  metrics: {
    fallback_count: number
    avg_deviation_ms: number
  }
}

export async function createMix(data: {
  song_title: string
  artist?: string
  source_type: string
  audio_asset_id?: string
  lyrics_text?: string
  language?: string
}): Promise<MixResponse> {
  const { data: resp } = await apiClient.post('/mixes', {
    ...data,
    auto_generate: true,
  })
  return resp
}

export async function getMixStatus(mixId: string): Promise<MixResponse> {
  const { data } = await apiClient.get(`/mixes/${mixId}`)
  return data
}

export async function generateTimeline(mixId: string): Promise<{ trace_id: string }> {
  const { data } = await apiClient.post(`/mixes/${mixId}/generate-timeline`)
  return data
}

export async function transcribeLyrics(mixId: string): Promise<{ trace_id: string; message: string }> {
  const { data } = await apiClient.post(`/mixes/${mixId}/transcribe`)
  return data
}

export async function importLyrics(mixId: string, lyricsText: string): Promise<{ message: string }> {
  const { data } = await apiClient.post(`/mixes/${mixId}/import-lyrics`, {
    lyrics_text: lyricsText,
  })
  return data
}

export async function updateLine(mixId: string, lineId: string, text: string): Promise<LineInfo> {
  const { data } = await apiClient.patch(`/mixes/${mixId}/lines/${lineId}`, { text })
  return data
}

export async function confirmLyrics(mixId: string): Promise<{ message: string }> {
  const { data } = await apiClient.post(`/mixes/${mixId}/confirm-lyrics`)
  return data
}

export async function matchVideos(mixId: string): Promise<{ trace_id: string; message: string }> {
  const { data } = await apiClient.post(`/mixes/${mixId}/match-videos`)
  return data
}

export async function getLines(mixId: string): Promise<{ lines: LineInfo[] }> {
  const { data } = await apiClient.get(`/mixes/${mixId}/lines`)
  return data
}

export async function getPreview(mixId: string): Promise<PreviewManifest> {
  const { data } = await apiClient.get(`/mixes/${mixId}/preview`)
  return data
}

export async function submitRender(mixId: string): Promise<{ job_id: string; status: string }> {
  const { data } = await apiClient.post(`/mixes/${mixId}/render`, {
    resolution: '1080p',
    frame_rate: 25,
  })
  return data
}

export async function getRenderStatus(mixId: string, jobId: string): Promise<{
  job_id: string
  status: string
  progress: number
  output_url: string | null
}> {
  const { data } = await apiClient.get(`/mixes/${mixId}/render`, {
    params: { job_id: jobId },
  })
  return data
}

export async function lockLine(
  mixId: string,
  lineId: string,
  selectedSegmentId?: string
): Promise<LineInfo> {
  const { data } = await apiClient.patch(`/mixes/${mixId}/lines/${lineId}`, {
    selected_segment_id: selectedSegmentId,
  })
  return data
}

export interface UploadResponse {
  id: string
  filename: string
  path: string
  size_bytes: number
}

export async function uploadAudio(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await apiClient.post('/admin/assets/audios/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return data
}
