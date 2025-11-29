import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { ArrowLeft, Loader2, CheckCircle, Play, RefreshCw, AlertCircle } from 'lucide-react'
import { getLines, getPreview, submitRender, lockLine } from '@/api/mix'

export default function Status() {
  const { mixId } = useParams<{ mixId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: linesData, isLoading: linesLoading, isFetching, error: linesError } = useQuery({
    queryKey: ['lines', mixId],
    queryFn: async () => {
      console.log('[Status] Fetching lines for mixId:', mixId)
      const result = await getLines(mixId!)
      console.log('[Status] Got lines:', result?.lines?.length)
      return result
    },
    enabled: !!mixId,
    placeholderData: keepPreviousData,
    staleTime: 5000, // 5秒内不重新获取
    refetchInterval: (query) => {
      // 如果还没有数据或者有行还在处理中，继续轮询
      const data = query.state.data
      if (!data || data.lines.length === 0) return 3000
      // 如果所有行都有候选了，停止轮询
      const allHaveCandidates = data.lines.every(l => l.candidates.length > 0 || l.status === 'locked')
      return allHaveCandidates ? false : 3000
    },
  })

  const { data: previewData } = useQuery({
    queryKey: ['preview', mixId],
    queryFn: () => getPreview(mixId!),
    enabled: !!mixId && (linesData?.lines?.some(l => l.status === 'locked') ?? false),
  })

  const lockMutation = useMutation({
    mutationFn: async ({ lineId, segmentId }: { lineId: string; segmentId: string }) => {
      console.log('[Status] Locking line:', lineId, 'segment:', segmentId)
      const result = await lockLine(mixId!, lineId, segmentId)
      console.log('[Status] Lock result:', result)
      return result
    },
    onSuccess: (data) => {
      console.log('[Status] Lock success, invalidating queries')
      // 不要立即 invalidate，而是等待一小段时间
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['lines', mixId] })
      }, 100)
    },
    onError: (error) => {
      console.error('[Status] Lock line failed:', error)
      alert('确认失败，请重试')
    },
  })

  const renderMutation = useMutation({
    mutationFn: () => submitRender(mixId!),
    onSuccess: (data) => {
      // 存储 job_id 用于结果页面查询
      sessionStorage.setItem(`job_${mixId}`, data.job_id)
      navigate(`/result/${mixId}`)
    },
    onError: (error) => {
      console.error('Submit render failed:', error)
      alert('提交渲染失败，请重试')
    },
  })

  const lines = linesData?.lines || []
  const lockedCount = lines.filter(l => l.status === 'locked').length
  const totalCount = lines.length
  const allLocked = totalCount > 0 && lockedCount === totalCount
  const linesWithCandidates = lines.filter(l => l.candidates.length > 0 || l.status === 'locked').length
  const isGenerating = totalCount === 0 || linesWithCandidates < totalCount

  // 调试信息
  console.log('[Status] Render state:', {
    linesLoading,
    isFetching,
    hasError: !!linesError,
    linesCount: lines.length,
    lockedCount,
    totalCount,
  })

  const handleLockAll = () => {
    const linesToLock = lines.filter(line => line.status !== 'locked' && line.candidates.length > 0)
    linesToLock.forEach(line => {
      lockMutation.mutate({ lineId: line.id, segmentId: line.candidates[0].id })
    })
  }

  const handleLockOne = (lineId: string, segmentId: string) => {
    lockMutation.mutate({ lineId, segmentId })
  }

  // 加载中状态
  if (linesLoading && totalCount === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-white animate-spin mx-auto mb-4" />
          <p className="text-white/80">正在加载...</p>
        </div>
      </div>
    )
  }

  // 错误状态
  if (linesError) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <p className="text-white/80">加载失败，请刷新页面重试</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto">
        <Link
          to="/create"
          className="inline-flex items-center gap-2 text-white/80 hover:text-white mb-8"
        >
          <ArrowLeft className="w-4 h-4" />
          返回
        </Link>

        <div className="bg-white rounded-2xl shadow-xl overflow-hidden">
          {/* Header */}
          <div className="bg-gradient-to-r from-purple-600 to-indigo-600 p-6">
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-white">混剪预览</h1>
              {isFetching && <Loader2 className="w-5 h-5 text-white/60 animate-spin" />}
            </div>
            {isGenerating ? (
              <>
                <p className="text-white/80 mt-1 flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  正在生成时间线... ({linesWithCandidates} / {totalCount || '?'})
                </p>
                <div className="mt-4 bg-white/20 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-white/60 h-full transition-all duration-500 animate-pulse"
                    style={{ width: totalCount > 0 ? `${(linesWithCandidates / totalCount) * 100}%` : '30%' }}
                  />
                </div>
              </>
            ) : (
              <>
                <p className="text-white/80 mt-1">
                  已确认 {lockedCount} / {totalCount} 句歌词
                </p>
                <div className="mt-4 bg-white/20 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-white h-full transition-all duration-500"
                    style={{ width: `${totalCount > 0 ? (lockedCount / totalCount) * 100 : 0}%` }}
                  />
                </div>
              </>
            )}
          </div>

          {/* Lines */}
          <div className="divide-y divide-gray-100 max-h-[400px] overflow-y-auto">
            {lines.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2" />
                正在分析音频，请稍候...
              </div>
            ) : (
              lines.map((line) => (
                <div
                  key={line.id}
                  className="p-4 flex items-center gap-4 hover:bg-gray-50"
                >
                  <div className="flex-shrink-0">
                    {line.status === 'locked' ? (
                      <CheckCircle className="w-5 h-5 text-green-500" />
                    ) : line.candidates.length > 0 ? (
                      <div className="w-5 h-5 border-2 border-purple-400 rounded-full" />
                    ) : (
                      <Loader2 className="w-5 h-5 text-gray-400 animate-spin" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-gray-900 truncate">{line.original_text}</p>
                    <p className="text-xs text-gray-500">
                      {(line.start_time_ms / 1000).toFixed(1)}s - {(line.end_time_ms / 1000).toFixed(1)}s
                      {line.candidates.length > 0 && ` | ${line.candidates.length} 个候选`}
                    </p>
                  </div>
                  {line.status !== 'locked' && line.candidates.length > 0 && (
                    <button
                      onClick={() => handleLockOne(line.id, line.candidates[0].id)}
                      disabled={lockMutation.isPending}
                      className="px-3 py-1 text-sm bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 disabled:opacity-50"
                    >
                      {lockMutation.isPending ? '...' : '确认'}
                    </button>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Actions */}
          <div className="p-6 bg-gray-50 flex items-center gap-4">
            <button
              onClick={handleLockAll}
              disabled={allLocked || lockMutation.isPending || isGenerating}
              className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-white disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RefreshCw className={`w-4 h-4 ${lockMutation.isPending ? 'animate-spin' : ''}`} />
              全部确认
            </button>
            <button
              onClick={() => renderMutation.mutate()}
              disabled={!allLocked || renderMutation.isPending}
              className="flex-1 flex items-center justify-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white py-3 rounded-xl font-semibold hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {renderMutation.isPending ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  提交中...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  生成视频
                </>
              )}
            </button>
          </div>

          {/* Preview Metrics */}
          {previewData?.metrics && (
            <div className="p-4 border-t border-gray-100 bg-gray-50">
              <p className="text-sm text-gray-600">
                预览指标：Fallback {previewData.metrics.fallback_count ?? 0} 句，
                平均偏差 {(previewData.metrics.avg_deviation_ms ?? 0).toFixed(0)}ms
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
