import { useQuery } from '@tanstack/react-query'
import {
  ListTodo,
  CheckCircle,
  XCircle,
  Clock,
  Film,
  Music,
  HardDrive,
  Activity
} from 'lucide-react'
import { getSystemStats, getHealth } from '@/api/config'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  if (hours > 0) return `${hours}h ${minutes % 60}m`
  if (minutes > 0) return `${minutes}m ${seconds % 60}s`
  return `${seconds}s`
}

export default function Dashboard() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['system-stats'],
    queryFn: getSystemStats,
    refetchInterval: 30000,
  })

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 30000,
  })

  if (statsLoading || healthLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  const taskStats = [
    { name: '总任务', value: stats?.tasks.total ?? 0, icon: ListTodo, color: 'text-gray-600 bg-gray-100' },
    { name: '待处理', value: stats?.tasks.pending ?? 0, icon: Clock, color: 'text-yellow-600 bg-yellow-100' },
    { name: '已完成', value: stats?.tasks.completed ?? 0, icon: CheckCircle, color: 'text-green-600 bg-green-100' },
    { name: '失败', value: stats?.tasks.failed ?? 0, icon: XCircle, color: 'text-red-600 bg-red-100' },
  ]

  return (
    <div className="space-y-6">
      {/* Task Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {taskStats.map((stat) => (
          <div key={stat.name} className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center gap-4">
              <div className={`rounded-lg p-3 ${stat.color}`}>
                <stat.icon className="h-6 w-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500">{stat.name}</p>
                <p className="text-2xl font-semibold text-gray-900">{stat.value}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Success Rate & Render Stats */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">渲染统计</h3>
          <dl className="space-y-4">
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">成功率</dt>
              <dd className="text-sm font-medium text-gray-900">
                {stats?.tasks.success_rate.toFixed(1)}%
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">总渲染任务</dt>
              <dd className="text-sm font-medium text-gray-900">{stats?.renders.total_jobs ?? 0}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">进行中</dt>
              <dd className="text-sm font-medium text-gray-900">{stats?.renders.in_progress ?? 0}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">平均渲染时长</dt>
              <dd className="text-sm font-medium text-gray-900">
                {stats?.renders.average_duration_ms
                  ? formatDuration(stats.renders.average_duration_ms)
                  : '-'}
              </dd>
            </div>
          </dl>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">存储统计</h3>
          <dl className="space-y-4">
            <div className="flex items-center justify-between">
              <dt className="flex items-center gap-2 text-sm text-gray-500">
                <Film className="h-4 w-4" />
                视频数量
              </dt>
              <dd className="text-sm font-medium text-gray-900">{stats?.storage.video_count ?? 0}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="flex items-center gap-2 text-sm text-gray-500">
                <HardDrive className="h-4 w-4" />
                视频占用
              </dt>
              <dd className="text-sm font-medium text-gray-900">
                {formatBytes(stats?.storage.video_size_bytes ?? 0)}
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="flex items-center gap-2 text-sm text-gray-500">
                <Music className="h-4 w-4" />
                音频数量
              </dt>
              <dd className="text-sm font-medium text-gray-900">{stats?.storage.audio_count ?? 0}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="flex items-center gap-2 text-sm text-gray-500">
                <HardDrive className="h-4 w-4" />
                音频占用
              </dt>
              <dd className="text-sm font-medium text-gray-900">
                {formatBytes(stats?.storage.audio_size_bytes ?? 0)}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Service Health */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-gray-900">服务状态</h3>
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
              health?.status === 'healthy'
                ? 'bg-green-100 text-green-800'
                : 'bg-red-100 text-red-800'
            }`}
          >
            <Activity className="h-3 w-3" />
            {health?.status === 'healthy' ? '正常' : '异常'}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {health?.services.map((service) => (
            <div
              key={service.name}
              className={`rounded-lg border p-4 ${
                service.status === 'healthy' || service.status === 'configured'
                  ? 'border-green-200 bg-green-50'
                  : service.status === 'not_configured'
                  ? 'border-yellow-200 bg-yellow-50'
                  : 'border-red-200 bg-red-50'
              }`}
            >
              <p className="text-sm font-medium text-gray-900 capitalize">
                {service.name.replace('_', ' ')}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {service.status}
                {service.latency_ms && ` (${service.latency_ms.toFixed(0)}ms)`}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
