import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { ArrowLeft, Loader2, CheckCircle, Play, RefreshCw, AlertCircle, Edit3, Check, X, Trash2, Plus } from 'lucide-react'
import { useState } from 'react'
import {
  getLines,
  getPreview,
  submitRender,
  lockLine,
  getMixStatus,
  updateLine,
  confirmLyrics,
  matchVideos,
  deleteLine,
  addLine,
} from '@/api/mix'

export default function Status() {
  const { mixId } = useParams<{ mixId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // 编辑状态
  const [editingLineId, setEditingLineId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')

  // 新增歌词表单状态
  const [showAddForm, setShowAddForm] = useState(false)
  const [newLyricText, setNewLyricText] = useState('')
  const [newLyricStartSec, setNewLyricStartSec] = useState('')
  const [newLyricEndSec, setNewLyricEndSec] = useState('')

  // 获取混剪任务状态（包含时间线进度和歌词行）
  const { data: mixData, isLoading: mixLoading } = useQuery({
    queryKey: ['mix', mixId],
    queryFn: () => getMixStatus(mixId!),
    enabled: !!mixId,
    refetchInterval: (query) => {
      const data = query.state.data
      // 如果还在识别或匹配中，继续轮询
      if (!data ||
          data.timeline_status === 'pending' ||
          data.timeline_status === 'transcribing' ||
          data.timeline_status === 'matching') {
        return 2000
      }
      return false
    },
  })

  const { data: linesData, isFetching } = useQuery({
    queryKey: ['lines', mixId],
    queryFn: () => getLines(mixId!),
    enabled: !!mixId && mixData?.timeline_status === 'generated',
    placeholderData: keepPreviousData,
    staleTime: 5000,
  })

  const { data: previewData } = useQuery({
    queryKey: ['preview', mixId],
    queryFn: () => getPreview(mixId!),
    enabled: !!mixId && (linesData?.lines?.some(l => l.status === 'locked') ?? false),
  })

  // 更新歌词行
  const updateLineMutation = useMutation({
    mutationFn: ({ lineId, text }: { lineId: string; text: string }) =>
      updateLine(mixId!, lineId, text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mix', mixId] })
      setEditingLineId(null)
      setEditText('')
    },
    onError: (error) => {
      console.error('Update line failed:', error)
      alert('更新失败，请重试')
    },
  })

  // 确认歌词
  const confirmLyricsMutation = useMutation({
    mutationFn: () => confirmLyrics(mixId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mix', mixId] })
    },
    onError: (error) => {
      console.error('Confirm lyrics failed:', error)
      alert('确认失败，请重试')
    },
  })

  // 触发视频匹配
  const matchVideosMutation = useMutation({
    mutationFn: () => matchVideos(mixId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mix', mixId] })
    },
    onError: (error) => {
      console.error('Match videos failed:', error)
      alert('匹配失败，请重试')
    },
  })

  // 删除歌词行
  const deleteLineMutation = useMutation({
    mutationFn: (lineId: string) => deleteLine(mixId!, lineId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mix', mixId] })
    },
    onError: (error) => {
      console.error('Delete line failed:', error)
      alert('删除失败，请重试')
    },
  })

  // 添加歌词行
  const addLineMutation = useMutation({
    mutationFn: (payload: { text: string; start_time_ms: number; end_time_ms: number }) =>
      addLine(mixId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mix', mixId] })
      setShowAddForm(false)
      setNewLyricText('')
      setNewLyricStartSec('')
      setNewLyricEndSec('')
    },
    onError: (error) => {
      console.error('Add line failed:', error)
      alert('添加失败，请重试')
    },
  })

  const lockMutation = useMutation({
    mutationFn: async ({ lineId, segmentId }: { lineId: string; segmentId: string }) => {
      return await lockLine(mixId!, lineId, segmentId)
    },
    onSuccess: () => {
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
      sessionStorage.setItem(`job_${mixId}`, data.job_id)
      navigate(`/result/${mixId}`)
    },
    onError: (error) => {
      console.error('Submit render failed:', error)
      alert('提交渲染失败，请重试')
    },
  })

  const timelineStatus = mixData?.timeline_status ?? 'pending'
  const timelineProgress = mixData?.timeline_progress ?? 0
  const lyricsConfirmed = mixData?.lyrics_confirmed ?? false

  // 从 mixData 获取歌词行（用于编辑阶段）
  const lyricsLines = mixData?.lines ?? []

  // 从 linesData 获取带候选的歌词行（用于确认阶段）
  const candidateLines = linesData?.lines ?? []
  // 有候选的行需要手动确认，没候选的行（fallback）视为已确认
  const linesNeedingLock = candidateLines.filter(l => l.candidates.length > 0)
  const lockedCount = linesNeedingLock.filter(l => l.status === 'locked').length
  const fallbackCount = candidateLines.filter(l => l.candidates.length === 0).length
  const totalNeedingLock = linesNeedingLock.length
  const allLocked = candidateLines.length > 0 && lockedCount === totalNeedingLock

  // 开始编辑
  const startEdit = (lineId: string, text: string) => {
    setEditingLineId(lineId)
    setEditText(text)
  }

  // 保存编辑
  const saveEdit = (lineId: string) => {
    if (editText.trim()) {
      updateLineMutation.mutate({ lineId, text: editText.trim() })
    }
  }

  // 取消编辑
  const cancelEdit = () => {
    setEditingLineId(null)
    setEditText('')
  }

  // 删除歌词行
  const handleDeleteLine = (lineId: string, text: string) => {
    if (confirm(`确定要删除这句歌词吗？\n"${text}"`)) {
      deleteLineMutation.mutate(lineId)
    }
  }

  // 提交新增歌词
  const handleAddLine = () => {
    const startMs = Math.round(parseFloat(newLyricStartSec) * 1000)
    const endMs = Math.round(parseFloat(newLyricEndSec) * 1000)

    if (!newLyricText.trim()) {
      alert('请输入歌词内容')
      return
    }
    if (isNaN(startMs) || isNaN(endMs)) {
      alert('请输入有效的时间')
      return
    }
    if (endMs <= startMs) {
      alert('结束时间必须大于开始时间')
      return
    }

    addLineMutation.mutate({
      text: newLyricText.trim(),
      start_time_ms: startMs,
      end_time_ms: endMs,
    })
  }

  // 确认歌词并开始匹配
  const handleConfirmAndMatch = async () => {
    try {
      await confirmLyricsMutation.mutateAsync()
      await matchVideosMutation.mutateAsync()
    } catch (error) {
      console.error('Confirm and match failed:', error)
    }
  }

  const handleLockAll = () => {
    const linesToLock = candidateLines.filter(line => line.status !== 'locked' && line.candidates.length > 0)
    linesToLock.forEach(line => {
      lockMutation.mutate({ lineId: line.id, segmentId: line.candidates[0].id })
    })
  }

  const handleLockOne = (lineId: string, segmentId: string) => {
    lockMutation.mutate({ lineId, segmentId })
  }

  // 获取阶段文本
  const getStageText = (): string => {
    switch (timelineStatus) {
      case 'pending':
        return '准备中...'
      case 'transcribing':
        if (timelineProgress < 20) return '准备识别音频...'
        if (timelineProgress < 80) return '识别歌词中...'
        return '处理识别结果...'
      case 'transcribed':
        return '歌词识别完成，请校对'
      case 'matching':
        if (timelineProgress < 10) return '准备匹配视频...'
        if (timelineProgress < 95) return '匹配视频片段中...'
        return '即将完成...'
      case 'generated':
        return '视频匹配完成'
      case 'error':
        return '处理出错'
      default:
        return '处理中...'
    }
  }

  // 加载中状态
  if (mixLoading) {
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
  if (timelineStatus === 'error') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
          <p className="text-white/80">处理失败，请返回重试</p>
          <Link to="/create" className="mt-4 inline-block text-purple-300 hover:text-purple-200">
            返回创建页面
          </Link>
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
              <h1 className="text-2xl font-bold text-white">
                {timelineStatus === 'transcribed' ? '歌词校对' :
                 timelineStatus === 'generated' ? '混剪预览' : '处理中'}
              </h1>
              {isFetching && <Loader2 className="w-5 h-5 text-white/60 animate-spin" />}
            </div>

            <p className="text-white/80 mt-1 flex items-center gap-2">
              {(timelineStatus === 'transcribing' || timelineStatus === 'matching' || timelineStatus === 'pending') && (
                <Loader2 className="w-4 h-4 animate-spin" />
              )}
              {getStageText()}
            </p>

            {/* 进度条 - 识别或匹配阶段显示 */}
            {(timelineStatus === 'transcribing' || timelineStatus === 'matching' || timelineStatus === 'pending') && (
              <div className="mt-2 flex items-center gap-3">
                <div className="flex-1 bg-white/20 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-white h-full transition-all duration-500"
                    style={{ width: `${timelineProgress}%` }}
                  />
                </div>
                <span className="text-white font-medium text-sm min-w-[3rem] text-right">
                  {Math.round(timelineProgress)}%
                </span>
              </div>
            )}

            {/* 确认进度 - 生成完成后显示 */}
            {timelineStatus === 'generated' && (
              <>
                <p className="text-white/80 mt-1">
                  已确认 {lockedCount} / {totalNeedingLock} 句歌词
                  {fallbackCount > 0 && ` (${fallbackCount} 句使用默认视频)`}
                </p>
                <div className="mt-2 bg-white/20 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-white h-full transition-all duration-500"
                    style={{ width: `${totalNeedingLock > 0 ? (lockedCount / totalNeedingLock) * 100 : 100}%` }}
                  />
                </div>
              </>
            )}
          </div>

          {/* 歌词编辑界面 - transcribed 状态时显示 */}
          {timelineStatus === 'transcribed' && (
            <>
              <div className="p-4 bg-yellow-50 border-b border-yellow-100">
                <p className="text-yellow-800 text-sm">
                  请检查以下歌词是否正确。如有错误，点击歌词进行编辑。确认无误后点击下方按钮开始匹配视频。
                </p>
              </div>
              <div className="divide-y divide-gray-100 max-h-[400px] overflow-y-auto">
                {lyricsLines.length === 0 ? (
                  <div className="p-8 text-center text-gray-500">
                    <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2" />
                    正在加载歌词...
                  </div>
                ) : (
                  lyricsLines.map((line) => (
                    <div
                      key={line.id}
                      className="p-4 flex items-center gap-4 hover:bg-gray-50"
                    >
                      <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center bg-purple-100 text-purple-600 rounded-full text-sm font-medium">
                        {line.line_no}
                      </div>
                      <div className="flex-1 min-w-0">
                        {editingLineId === line.id ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={editText}
                              onChange={(e) => setEditText(e.target.value)}
                              className="flex-1 px-3 py-1.5 border border-purple-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                              autoFocus
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') saveEdit(line.id)
                                if (e.key === 'Escape') cancelEdit()
                              }}
                            />
                            <button
                              onClick={() => saveEdit(line.id)}
                              disabled={updateLineMutation.isPending}
                              className="p-1.5 text-green-600 hover:bg-green-50 rounded"
                            >
                              <Check className="w-5 h-5" />
                            </button>
                            <button
                              onClick={cancelEdit}
                              className="p-1.5 text-gray-400 hover:bg-gray-50 rounded"
                            >
                              <X className="w-5 h-5" />
                            </button>
                          </div>
                        ) : (
                          <div
                            className="cursor-pointer group flex items-center gap-2"
                            onClick={() => startEdit(line.id, line.original_text)}
                          >
                            <p className="text-gray-900">{line.original_text}</p>
                            <Edit3 className="w-4 h-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                          </div>
                        )}
                        <p className="text-xs text-gray-500 mt-1">
                          {(line.start_time_ms / 1000).toFixed(1)}s - {(line.end_time_ms / 1000).toFixed(1)}s
                        </p>
                      </div>
                      {/* 删除按钮 */}
                      <button
                        onClick={() => handleDeleteLine(line.id, line.original_text)}
                        disabled={deleteLineMutation.isPending}
                        className="flex-shrink-0 p-2 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
                        title="删除此行"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))
                )}
              </div>

              {/* 新增歌词区域 */}
              <div className="p-4 border-t border-gray-100">
                {showAddForm ? (
                  <div className="bg-purple-50 rounded-lg p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="font-medium text-purple-900">添加新歌词</h4>
                      <button
                        onClick={() => setShowAddForm(false)}
                        className="text-gray-400 hover:text-gray-600"
                      >
                        <X className="w-5 h-5" />
                      </button>
                    </div>
                    <input
                      type="text"
                      placeholder="输入歌词内容"
                      value={newLyricText}
                      onChange={(e) => setNewLyricText(e.target.value)}
                      className="w-full px-3 py-2 border border-purple-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                    />
                    <div className="flex gap-3">
                      <div className="flex-1">
                        <label className="text-xs text-gray-500 mb-1 block">开始时间 (秒)</label>
                        <input
                          type="number"
                          step="0.1"
                          placeholder="如: 26.5"
                          value={newLyricStartSec}
                          onChange={(e) => setNewLyricStartSec(e.target.value)}
                          className="w-full px-3 py-2 border border-purple-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                        />
                      </div>
                      <div className="flex-1">
                        <label className="text-xs text-gray-500 mb-1 block">结束时间 (秒)</label>
                        <input
                          type="number"
                          step="0.1"
                          placeholder="如: 28.0"
                          value={newLyricEndSec}
                          onChange={(e) => setNewLyricEndSec(e.target.value)}
                          className="w-full px-3 py-2 border border-purple-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                        />
                      </div>
                    </div>
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => setShowAddForm(false)}
                        className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                      >
                        取消
                      </button>
                      <button
                        onClick={handleAddLine}
                        disabled={addLineMutation.isPending}
                        className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
                      >
                        {addLineMutation.isPending ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            添加中...
                          </>
                        ) : (
                          '确认添加'
                        )}
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => setShowAddForm(true)}
                    className="w-full flex items-center justify-center gap-2 py-2 border-2 border-dashed border-purple-300 text-purple-600 rounded-lg hover:bg-purple-50 hover:border-purple-400 transition-colors"
                  >
                    <Plus className="w-5 h-5" />
                    添加歌词
                  </button>
                )}
              </div>

              <div className="p-6 bg-gray-50">
                <button
                  onClick={handleConfirmAndMatch}
                  disabled={confirmLyricsMutation.isPending || matchVideosMutation.isPending || lyricsLines.length === 0}
                  className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white py-3 rounded-xl font-semibold hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {(confirmLyricsMutation.isPending || matchVideosMutation.isPending) ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      处理中...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-5 h-5" />
                      确认歌词并开始匹配视频
                    </>
                  )}
                </button>
              </div>
            </>
          )}

          {/* 视频匹配进度 - matching 状态时显示 */}
          {timelineStatus === 'matching' && (
            <div className="p-8 text-center">
              <Loader2 className="w-12 h-12 text-purple-600 animate-spin mx-auto mb-4" />
              <p className="text-gray-600">正在为每句歌词匹配最佳视频片段...</p>
              <p className="text-gray-400 text-sm mt-2">这可能需要几分钟，请耐心等待</p>
            </div>
          )}

          {/* 识别进度 - transcribing 状态时显示 */}
          {(timelineStatus === 'transcribing' || timelineStatus === 'pending') && (
            <div className="p-8 text-center">
              <Loader2 className="w-12 h-12 text-purple-600 animate-spin mx-auto mb-4" />
              <p className="text-gray-600">正在识别音频中的歌词...</p>
              <p className="text-gray-400 text-sm mt-2">识别完成后您可以校对歌词内容</p>
            </div>
          )}

          {/* 视频确认界面 - generated 状态时显示 */}
          {timelineStatus === 'generated' && (
            <>
              <div className="divide-y divide-gray-100 max-h-[400px] overflow-y-auto">
                {candidateLines.length === 0 ? (
                  <div className="p-8 text-center text-gray-500">
                    <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2" />
                    正在加载...
                  </div>
                ) : (
                  candidateLines.map((line) => (
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
                          <AlertCircle className="w-5 h-5 text-orange-400" title="使用默认视频" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-gray-900 truncate">{line.original_text}</p>
                        <p className="text-xs text-gray-500">
                          {(line.start_time_ms / 1000).toFixed(1)}s - {(line.end_time_ms / 1000).toFixed(1)}s
                          {line.candidates.length > 0
                            ? ` | ${line.candidates.length} 个候选`
                            : ' | 默认视频'}
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
                  disabled={allLocked || lockMutation.isPending}
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
            </>
          )}
        </div>
      </div>
    </div>
  )
}
