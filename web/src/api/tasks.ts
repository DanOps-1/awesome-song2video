import apiClient from './client'
import type { TaskListResponse, TaskDetail } from '@/types'

interface ListTasksParams {
  page?: number
  page_size?: number
  status?: string
  keyword?: string
}

export async function listTasks(params: ListTasksParams = {}): Promise<TaskListResponse> {
  const { data } = await apiClient.get('/admin/tasks', { params })
  return data
}

export async function getTask(taskId: string): Promise<TaskDetail> {
  const { data } = await apiClient.get(`/admin/tasks/${taskId}`)
  return data
}

export async function retryTask(taskId: string): Promise<{ message: string }> {
  const { data } = await apiClient.post(`/admin/tasks/${taskId}/retry`)
  return data
}

export async function deleteTask(taskId: string): Promise<void> {
  await apiClient.delete(`/admin/tasks/${taskId}`)
}

export async function getTaskLogs(taskId: string): Promise<{ task_id: string; logs: unknown[] }> {
  const { data } = await apiClient.get(`/admin/tasks/${taskId}/logs`)
  return data
}

export async function cancelRenderJob(taskId: string, jobId: string): Promise<{ message: string }> {
  const { data } = await apiClient.post(`/admin/tasks/${taskId}/render-jobs/${jobId}/cancel`)
  return data
}
