import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Music,
  Film,
  Clock,
  CheckCircle,
  XCircle,
  FileText,
  Loader2,
  StopCircle,
  Ban
} from 'lucide-react'
import { getTask, getTaskLogs, cancelRenderJob } from '@/api/tasks'

export default function TaskDetail() {
  const { taskId } = useParams<{ taskId: string }>()
  const queryClient = useQueryClient()

  const cancelMutation = useMutation({
    mutationFn: ({ jobId }: { jobId: string }) => cancelRenderJob(taskId!, jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task', taskId] })
    },
    onError: (error) => {
      console.error('Cancel render job failed:', error)
      alert('取消失败，请重试')
    },
  })

  const { data: task, isLoading: taskLoading } = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => getTask(taskId!),
    enabled: !!taskId,
    // 当有渲染任务正在运行时，每3秒自动刷新
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return false
      const hasRunningJob = data.render_jobs?.some(
        (job: { job_status: string }) => job.job_status === 'running' || job.job_status === 'queued'
      )
      return hasRunningJob ? 3000 : false
    },
  })

  const { data: logsData } = useQuery({
    queryKey: ['task-logs', taskId],
    queryFn: () => getTaskLogs(taskId!),
    enabled: !!taskId,
  })

  if (taskLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!task) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">任务不存在</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          to="/tasks"
          className="p-2 rounded-lg hover:bg-gray-100"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h2 className="text-xl font-semibold text-gray-900">{task.song_title}</h2>
          <p className="text-sm text-gray-500">{task.artist || '未知艺术家'}</p>
        </div>
      </div>

      {/* Info Cards */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Basic Info */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">基本信息</h3>
          <dl className="space-y-3">
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">任务 ID</dt>
              <dd className="text-sm font-mono text-gray-900">{task.id.slice(0, 8)}...</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">来源类型</dt>
              <dd className="text-sm text-gray-900">{task.source_type}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">语言</dt>
              <dd className="text-sm text-gray-900">{task.language}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">优先级</dt>
              <dd className="text-sm text-gray-900">{task.priority}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">创建时间</dt>
              <dd className="text-sm text-gray-900">
                {task.created_at ? new Date(task.created_at).toLocaleString('zh-CN') : '-'}
              </dd>
            </div>
          </dl>
        </div>

        {/* Status */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">状态</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">时间线状态</span>
              <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                task.timeline_status === 'generated' ? 'bg-green-100 text-green-800' :
                task.timeline_status === 'failed' ? 'bg-red-100 text-red-800' :
                'bg-yellow-100 text-yellow-800'
              }`}>
                {task.timeline_status}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">渲染状态</span>
              <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                task.render_status === 'completed' || task.render_status === 'success' ? 'bg-green-100 text-green-800' :
                task.render_status === 'failed' ? 'bg-red-100 text-red-800' :
                task.render_status === 'running' ? 'bg-blue-100 text-blue-800' :
                'bg-yellow-100 text-yellow-800'
              }`}>
                {task.render_status === 'queued' ? '排队中' :
                 task.render_status === 'running' ? '渲染中' :
                 task.render_status === 'success' ? '已完成' :
                 task.render_status}
              </span>
            </div>
          </div>
        </div>

        {/* Metrics */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">指标</h3>
          {task.metrics ? (
            <pre className="text-xs text-gray-600 bg-gray-50 rounded-lg p-3 overflow-auto max-h-32">
              {JSON.stringify(task.metrics, null, 2)}
            </pre>
          ) : (
            <p className="text-sm text-gray-500">暂无指标数据</p>
          )}
        </div>
      </div>

      {/* Lines */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">
          歌词行 ({task.lines.length})
        </h3>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">#</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">歌词</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">时间</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">状态</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">候选数</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {task.lines.map((line) => (
                <tr key={line.id} className="hover:bg-gray-50">
                  <td className="px-4 py-2 text-sm text-gray-500">{line.line_no}</td>
                  <td className="px-4 py-2 text-sm text-gray-900 max-w-xs truncate">
                    {line.original_text}
                  </td>
                  <td className="px-4 py-2 text-sm text-gray-500">
                    {(line.start_time_ms / 1000).toFixed(1)}s - {(line.end_time_ms / 1000).toFixed(1)}s
                  </td>
                  <td className="px-4 py-2">
                    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                      line.status === 'locked' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                      {line.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-sm text-gray-500">{line.candidates_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Render Jobs */}
      {task.render_jobs.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">
            渲染任务 ({task.render_jobs.length})
          </h3>
          <div className="space-y-3">
            {task.render_jobs.map((job) => (
              <div
                key={job.id}
                className={`border rounded-lg p-4 ${
                  job.job_status === 'success' ? 'border-green-200 bg-green-50' :
                  job.job_status === 'failed' ? 'border-red-200 bg-red-50' :
                  job.job_status === 'cancelled' ? 'border-orange-200 bg-orange-50' :
                  job.job_status === 'running' ? 'border-blue-200 bg-blue-50' :
                  'border-gray-200'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {job.job_status === 'success' ? (
                      <CheckCircle className="h-5 w-5 text-green-600" />
                    ) : job.job_status === 'failed' ? (
                      <XCircle className="h-5 w-5 text-red-600" />
                    ) : job.job_status === 'cancelled' ? (
                      <Ban className="h-5 w-5 text-orange-600" />
                    ) : job.job_status === 'running' ? (
                      <Loader2 className="h-5 w-5 text-blue-600 animate-spin" />
                    ) : (
                      <Clock className="h-5 w-5 text-yellow-600" />
                    )}
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        Job {job.id.slice(0, 8)}
                      </p>
                      <p className="text-xs text-gray-500">
                        提交于 {job.submitted_at ? new Date(job.submitted_at).toLocaleString('zh-CN') : '-'}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <p className="text-sm font-medium">
                        {job.job_status === 'queued' ? '排队中' :
                         job.job_status === 'running' ? '渲染中' :
                         job.job_status === 'success' ? '已完成' :
                         job.job_status === 'failed' ? '失败' :
                         job.job_status === 'cancelled' ? '已取消' :
                         job.job_status}
                      </p>
                      {job.progress > 0 && job.progress < 100 && (
                        <p className="text-xs text-gray-500">{job.progress.toFixed(0)}%</p>
                      )}
                    </div>
                    {(job.job_status === 'queued' || job.job_status === 'running') && (
                      <button
                        onClick={() => {
                          if (confirm('确定要取消这个渲染任务吗?')) {
                            cancelMutation.mutate({ jobId: job.id })
                          }
                        }}
                        disabled={cancelMutation.isPending}
                        className="p-2 text-orange-600 hover:bg-orange-100 rounded-lg transition-colors"
                        title="取消渲染"
                      >
                        <StopCircle className="h-5 w-5" />
                      </button>
                    )}
                  </div>
                </div>
                {job.error_log && (
                  <div className="mt-3 p-3 bg-red-100 rounded text-xs text-red-800 font-mono">
                    {job.error_log}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Logs */}
      {logsData?.logs && logsData.logs.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center gap-2">
            <FileText className="h-5 w-5" />
            日志
          </h3>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {(logsData.logs as Array<{ timestamp: string; level: string; message: string }>).map((log, i) => (
              <div
                key={i}
                className={`text-sm p-2 rounded ${
                  log.level === 'ERROR' ? 'bg-red-50 text-red-800' : 'bg-gray-50 text-gray-800'
                }`}
              >
                <span className="text-xs text-gray-500 mr-2">
                  {new Date(log.timestamp).toLocaleString('zh-CN')}
                </span>
                <span className={`font-medium mr-2 ${log.level === 'ERROR' ? 'text-red-600' : 'text-gray-600'}`}>
                  [{log.level}]
                </span>
                {log.message}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
