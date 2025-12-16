import apiClient from './client'
import type { VideoListResponse, AudioListResponse } from '@/types'

interface ListParams {
  page?: number
  page_size?: number
  keyword?: string
}

export async function listVideos(params: ListParams = {}): Promise<VideoListResponse> {
  const { data } = await apiClient.get('/admin/assets/videos', { params })
  return data
}

export async function uploadVideo(file: File): Promise<{ id: string; filename: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await apiClient.post('/admin/assets/videos/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function deleteVideo(videoId: string): Promise<void> {
  await apiClient.delete(`/admin/assets/videos/${videoId}`)
}

export async function getVideoIndexStatus(videoId: string): Promise<{
  video_id: string
  index_id: string | null
  status: string
}> {
  const { data } = await apiClient.get(`/admin/assets/videos/${videoId}/index-status`)
  return data
}

export async function reindexVideo(videoId: string): Promise<{ message: string }> {
  const { data } = await apiClient.post(`/admin/assets/videos/${videoId}/reindex`)
  return data
}

export async function listAudios(params: ListParams = {}): Promise<AudioListResponse> {
  const { data } = await apiClient.get('/admin/assets/audios', { params })
  return data
}

export async function uploadAudio(file: File): Promise<{ id: string; filename: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await apiClient.post('/admin/assets/audios/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function deleteAudio(audioId: string): Promise<void> {
  await apiClient.delete(`/admin/assets/audios/${audioId}`)
}
