import apiClient from './client'
import type { SystemConfig, SystemStats, HealthResponse } from '@/types'

export async function getConfig(): Promise<SystemConfig> {
  const { data } = await apiClient.get('/admin/config')
  return data
}

export async function updateConfig(updates: Partial<{
  retriever_backend: 'twelvelabs' | 'clip' | 'vlm'
  render_concurrency_limit: number
  render_clip_concurrency: number
  render_per_video_limit: number
  render_max_retry: number
  query_rewrite_enabled: boolean
  query_rewrite_mandatory: boolean
}>): Promise<SystemConfig> {
  const { data } = await apiClient.patch('/admin/config', updates)
  return data
}

export async function getRetrieverStatus(): Promise<{
  current_backend: string
  available_backends: string[]
  backend_status: Record<string, { available: boolean; reason: string }>
}> {
  const { data } = await apiClient.get('/admin/config/retriever')
  return data
}

export async function switchRetriever(backend: 'twelvelabs' | 'clip' | 'vlm'): Promise<{
  message: string
  current_backend: string
  requested_backend: string
}> {
  const { data } = await apiClient.post('/admin/config/retriever/switch', { backend })
  return data
}

export async function getSystemStats(): Promise<SystemStats> {
  const { data } = await apiClient.get('/admin/system/stats')
  return data
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get('/admin/system/health')
  return data
}
