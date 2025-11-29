import { useLocation } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'

const titles: Record<string, string> = {
  '/dashboard': '仪表盘',
  '/tasks': '任务管理',
  '/assets/videos': '视频库',
  '/assets/audios': '音频库',
  '/settings': '系统配置',
  '/settings/retriever': '检索后端配置',
}

export default function Header() {
  const location = useLocation()
  const queryClient = useQueryClient()

  const title = titles[location.pathname] || '详情'

  const handleRefresh = () => {
    queryClient.invalidateQueries()
  }

  return (
    <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-gray-200 bg-white px-6">
      <h1 className="text-xl font-semibold text-gray-900">{title}</h1>
      <button
        onClick={handleRefresh}
        className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
      >
        <RefreshCw className="h-4 w-4" />
        刷新
      </button>
    </header>
  )
}
