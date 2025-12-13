import { useState, useEffect, useRef } from 'react'
import { Play, Pause, Trash2, Filter, RefreshCw } from 'lucide-react'

interface LogEntry {
  timestamp?: string
  level?: string
  event?: string
  raw: string
}

const LEVEL_COLORS: Record<string, string> = {
  info: 'text-blue-600 bg-blue-50',
  warning: 'text-yellow-600 bg-yellow-50',
  error: 'text-red-600 bg-red-50',
  debug: 'text-gray-500 bg-gray-50',
}

export default function LogViewer() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [filter, setFilter] = useState('')
  const [levelFilter, setLevelFilter] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [loading, setLoading] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  // 获取历史日志
  const fetchLogs = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ lines: '200' })
      if (filter) params.set('filter', filter)
      if (levelFilter) params.set('level', levelFilter)

      const res = await fetch(`/api/v1/admin/logs?${params}`)
      const data = await res.json()
      setLogs(data.lines || [])
    } catch (err) {
      console.error('Failed to fetch logs:', err)
    } finally {
      setLoading(false)
    }
  }

  // 开始实时流
  const startStreaming = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    const params = new URLSearchParams()
    if (filter) params.set('filter', filter)

    const es = new EventSource(`/api/v1/admin/logs/stream?${params}`)

    es.onmessage = (event) => {
      try {
        const entry = JSON.parse(event.data) as LogEntry
        if (entry.raw) {
          setLogs(prev => [...prev.slice(-500), entry]) // 保留最近500条
        }
      } catch (err) {
        console.error('Failed to parse log:', err)
      }
    }

    es.onerror = () => {
      console.error('EventSource error')
      setIsStreaming(false)
    }

    eventSourceRef.current = es
    setIsStreaming(true)
  }

  // 停止实时流
  const stopStreaming = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setIsStreaming(false)
  }

  // 清空日志
  const clearLogs = () => {
    setLogs([])
  }

  // 自动滚动到底部
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  // 初始加载
  useEffect(() => {
    fetchLogs()
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  // 格式化时间戳
  const formatTime = (timestamp?: string) => {
    if (!timestamp) return ''
    try {
      const date = new Date(timestamp)
      return date.toLocaleTimeString('zh-CN', { hour12: false })
    } catch {
      return timestamp
    }
  }

  // 高亮关键词
  const highlightKeywords = (text: string) => {
    const keywords = ['beat', 'sync', 'offset', 'bpm', 'tempo']
    let result = text
    keywords.forEach(kw => {
      const regex = new RegExp(`(${kw})`, 'gi')
      result = result.replace(regex, '<mark class="bg-yellow-200 px-0.5 rounded">$1</mark>')
    })
    return result
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">实时日志</h1>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-1 text-xs rounded-full ${isStreaming ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
            {isStreaming ? '● 实时' : '○ 暂停'}
          </span>
        </div>
      </div>

      {/* 工具栏 */}
      <div className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200">
        <div className="flex items-center gap-2 flex-1">
          <Filter className="h-4 w-4 text-gray-400" />
          <input
            type="text"
            placeholder="过滤关键词（如 beat, render, error）"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="flex-1 px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        <select
          value={levelFilter}
          onChange={(e) => setLevelFilter(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
        >
          <option value="">全部级别</option>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
        </select>

        <div className="flex items-center gap-1 border-l border-gray-200 pl-3">
          <button
            onClick={fetchLogs}
            disabled={loading}
            className="p-2 text-gray-600 hover:bg-gray-100 rounded-md"
            title="刷新"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>

          {isStreaming ? (
            <button
              onClick={stopStreaming}
              className="p-2 text-yellow-600 hover:bg-yellow-50 rounded-md"
              title="暂停实时"
            >
              <Pause className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={startStreaming}
              className="p-2 text-green-600 hover:bg-green-50 rounded-md"
              title="开始实时"
            >
              <Play className="h-4 w-4" />
            </button>
          )}

          <button
            onClick={clearLogs}
            className="p-2 text-red-600 hover:bg-red-50 rounded-md"
            title="清空"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>

        <label className="flex items-center gap-2 text-sm text-gray-600 border-l border-gray-200 pl-3">
          <input
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="rounded border-gray-300"
          />
          自动滚动
        </label>
      </div>

      {/* 快捷过滤按钮 */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">快捷过滤：</span>
        {['beat', 'render', 'timeline', 'error', 'warning'].map(kw => (
          <button
            key={kw}
            onClick={() => {
              setFilter(kw)
              fetchLogs()
            }}
            className={`px-2 py-1 text-xs rounded-full border ${
              filter === kw
                ? 'bg-primary-100 text-primary-700 border-primary-300'
                : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'
            }`}
          >
            {kw}
          </button>
        ))}
        {filter && (
          <button
            onClick={() => {
              setFilter('')
              fetchLogs()
            }}
            className="px-2 py-1 text-xs text-gray-500 hover:text-gray-700"
          >
            清除过滤
          </button>
        )}
      </div>

      {/* 日志列表 */}
      <div className="bg-gray-900 rounded-lg overflow-hidden">
        <div className="h-[600px] overflow-y-auto p-4 font-mono text-xs">
          {logs.length === 0 ? (
            <div className="text-gray-500 text-center py-8">
              暂无日志，点击"开始实时"查看实时日志
            </div>
          ) : (
            logs.map((log, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2 py-1 hover:bg-gray-800 rounded px-2 -mx-2"
              >
                {log.timestamp && (
                  <span className="text-gray-500 shrink-0">
                    {formatTime(log.timestamp)}
                  </span>
                )}
                {log.level && (
                  <span className={`px-1.5 py-0.5 rounded text-xs uppercase shrink-0 ${LEVEL_COLORS[log.level] || 'text-gray-400'}`}>
                    {log.level}
                  </span>
                )}
                {log.event && (
                  <span className="text-cyan-400 shrink-0">{log.event}</span>
                )}
                <span
                  className="text-gray-300 break-all"
                  dangerouslySetInnerHTML={{ __html: highlightKeywords(log.raw) }}
                />
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>
      </div>

      {/* 统计信息 */}
      <div className="flex items-center justify-between text-sm text-gray-500">
        <span>共 {logs.length} 条日志</span>
        <span>提示：点击"开始实时"可查看实时日志流</span>
      </div>
    </div>
  )
}
