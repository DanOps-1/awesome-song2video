import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  Search,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Trash2,
  Eye,
  Clock,
  CheckCircle,
  XCircle,
  Loader2
} from 'lucide-react'
import { listTasks, retryTask, deleteTask } from '@/api/tasks'

const statusConfig: Record<string, { label: string; icon: React.ElementType; color: string }> = {
  // 通用状态
  pending: { label: '待处理', icon: Clock, color: 'text-yellow-600 bg-yellow-100' },
  processing: { label: '处理中', icon: Loader2, color: 'text-blue-600 bg-blue-100' },
  generated: { label: '已生成', icon: CheckCircle, color: 'text-green-600 bg-green-100' },
  completed: { label: '已完成', icon: CheckCircle, color: 'text-green-600 bg-green-100' },
  failed: { label: '失败', icon: XCircle, color: 'text-red-600 bg-red-100' },
  // 渲染任务专用状态
  queued: { label: '排队中', icon: Clock, color: 'text-yellow-600 bg-yellow-100' },
  running: { label: '渲染中', icon: Loader2, color: 'text-blue-600 bg-blue-100' },
  success: { label: '已完成', icon: CheckCircle, color: 'text-green-600 bg-green-100' },
  cancelled: { label: '已取消', icon: XCircle, color: 'text-orange-600 bg-orange-100' },
}

export default function TaskList() {
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<string>('')
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['tasks', page, keyword, status],
    queryFn: () => listTasks({ page, page_size: 20, keyword: keyword || undefined, status: status || undefined }),
    // 当有处理中的任务时，每5秒自动刷新
    refetchInterval: (query) => {
      const result = query.state.data
      if (!result?.stats) return false
      return (result.stats.processing > 0) ? 5000 : false
    },
  })

  const retryMutation = useMutation({
    mutationFn: retryTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
  }

  return (
    <div className="space-y-4">
      {/* Stats */}
      {data?.stats && (
        <div className="grid grid-cols-5 gap-4">
          <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
            <p className="text-2xl font-semibold text-gray-900">{data.stats.total}</p>
            <p className="text-sm text-gray-500">总计</p>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
            <p className="text-2xl font-semibold text-yellow-600">{data.stats.pending}</p>
            <p className="text-sm text-gray-500">待处理</p>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
            <p className="text-2xl font-semibold text-blue-600">{data.stats.processing}</p>
            <p className="text-sm text-gray-500">处理中</p>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
            <p className="text-2xl font-semibold text-green-600">{data.stats.completed}</p>
            <p className="text-sm text-gray-500">已完成</p>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
            <p className="text-2xl font-semibold text-red-600">{data.stats.failed}</p>
            <p className="text-sm text-gray-500">失败</p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <form onSubmit={handleSearch} className="flex gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="搜索歌曲名或歌手..."
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            />
          </div>
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(1) }}
            className="border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">全部状态</option>
            <option value="pending">待处理</option>
            <option value="processing">处理中</option>
            <option value="completed">已完成</option>
            <option value="failed">失败</option>
          </select>
          <button
            type="submit"
            className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
          >
            搜索
          </button>
        </form>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
          </div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  歌曲信息
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  时间线状态
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  渲染状态
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  创建时间
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  操作
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {data?.tasks.map((task) => {
                const timelineStatus = statusConfig[task.timeline_status] || statusConfig.pending
                const renderStatus = statusConfig[task.render_status] || statusConfig.pending
                const isFailed = task.timeline_status === 'failed' || task.render_status === 'failed'

                return (
                  <tr key={task.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium text-gray-900">{task.song_title}</p>
                        <p className="text-sm text-gray-500">{task.artist || '未知艺术家'}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${timelineStatus.color}`}>
                        <timelineStatus.icon className="h-3 w-3" />
                        {timelineStatus.label}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${renderStatus.color}`}>
                        <renderStatus.icon className="h-3 w-3" />
                        {renderStatus.label}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {task.created_at ? new Date(task.created_at).toLocaleString('zh-CN') : '-'}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          to={`/tasks/${task.id}`}
                          className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
                          title="查看详情"
                        >
                          <Eye className="h-4 w-4" />
                        </Link>
                        {isFailed && (
                          <button
                            onClick={() => retryMutation.mutate(task.id)}
                            disabled={retryMutation.isPending}
                            className="p-2 text-gray-400 hover:text-blue-600 rounded-lg hover:bg-blue-50"
                            title="重试"
                          >
                            <RotateCcw className="h-4 w-4" />
                          </button>
                        )}
                        <button
                          onClick={() => {
                            if (confirm('确定删除此任务?')) {
                              deleteMutation.mutate(task.id)
                            }
                          }}
                          disabled={deleteMutation.isPending}
                          className="p-2 text-gray-400 hover:text-red-600 rounded-lg hover:bg-red-50"
                          title="删除"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}

        {/* Pagination */}
        {data && data.total_pages > 1 && (
          <div className="flex items-center justify-between border-t border-gray-200 px-6 py-3">
            <p className="text-sm text-gray-500">
              第 {data.page} 页，共 {data.total_pages} 页
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-2 border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                disabled={page === data.total_pages}
                className="p-2 border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
