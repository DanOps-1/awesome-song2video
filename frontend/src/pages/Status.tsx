import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { ArrowLeft, Loader2, CheckCircle, Play, RefreshCw, AlertCircle, Edit3, Check, X, Trash2, Plus, ChevronDown, ChevronUp, Video } from 'lucide-react'
import { useState } from 'react'
import {
  getLines,
  getPreview,
  submitRender,
  lockLine,
  getMixStatus,
  updateLine,
  confirmLyrics,
  unconfirmLyrics,
  matchVideos,
  deleteLine,
  deleteLinesBatch,
  addLine,
  getCandidatePreviewUrl,
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

  // 多选删除状态
  const [isSelectMode, setIsSelectMode] = useState(false)
  const [selectedLineIds, setSelectedLineIds] = useState<Set<string>>(new Set())

  // 渲染选项
  const [bilingualSubtitle, setBilingualSubtitle] = useState(false)

  // 候选视频展开/预览状态
  const [expandedLineIds, setExpandedLineIds] = useState<Set<string>>(new Set())
  const [previewingCandidate, setPreviewingCandidate] = useState<{
    lineId: string
    candidateId: string
  } | null>(null)

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

  // 返回修改歌词（重置所有匹配）
  const unconfirmLyricsMutation = useMutation({
    mutationFn: () => unconfirmLyrics(mixId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mix', mixId] })
      queryClient.invalidateQueries({ queryKey: ['lines', mixId] })
    },
    onError: (error) => {
      console.error('Unconfirm lyrics failed:', error)
      alert('操作失败，请重试')
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

  // 批量删除歌词行
  const deleteLinesBatchMutation = useMutation({
    mutationFn: (lineIds: string[]) => deleteLinesBatch(mixId!, lineIds),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['mix', mixId] })
      setSelectedLineIds(new Set())
      setIsSelectMode(false)
      alert(data.message)
    },
    onError: (error) => {
      console.error('Batch delete failed:', error)
      alert('批量删除失败，请重试')
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
    mutationFn: () => submitRender(mixId!, { bilingual_subtitle: bilingualSubtitle }),
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
  // lyricsConfirmed 在合并界面后暂不使用
  const _lyricsConfirmed = mixData?.lyrics_confirmed ?? false
  void _lyricsConfirmed

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

  // 切换选中状态
  const toggleLineSelection = (lineId: string) => {
    setSelectedLineIds(prev => {
      const newSet = new Set(prev)
      if (newSet.has(lineId)) {
        newSet.delete(lineId)
      } else {
        newSet.add(lineId)
      }
      return newSet
    })
  }

  // 全选/取消全选
  const toggleSelectAll = () => {
    if (selectedLineIds.size === lyricsLines.length) {
      setSelectedLineIds(new Set())
    } else {
      setSelectedLineIds(new Set(lyricsLines.map(l => l.id)))
    }
  }

  // 批量删除
  const handleBatchDelete = () => {
    if (selectedLineIds.size === 0) return
    if (confirm(`确定要删除选中的 ${selectedLineIds.size} 句歌词吗？`)) {
      deleteLinesBatchMutation.mutate(Array.from(selectedLineIds))
    }
  }

  // 退出多选模式
  const exitSelectMode = () => {
    setIsSelectMode(false)
    setSelectedLineIds(new Set())
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
      // 使用已选择的片段，否则使用第一个
      const segmentId = line.selected_segment_id || line.candidates[0].id
      lockMutation.mutate({ lineId: line.id, segmentId })
    })
  }

  const handleLockOne = (lineId: string, segmentId: string) => {
    lockMutation.mutate({ lineId, segmentId })
  }

  // 切换歌词行的候选列表展开/收起
  const toggleLineExpansion = (lineId: string) => {
    setExpandedLineIds(prev => {
      const newSet = new Set(prev)
      if (newSet.has(lineId)) {
        newSet.delete(lineId)
      } else {
        newSet.add(lineId)
      }
      return newSet
    })
  }

  // 选择候选视频（不立即锁定，只是选择）
  const handleSelectCandidate = (lineId: string, candidateId: string) => {
    lockMutation.mutate({ lineId, segmentId: candidateId })
    setPreviewingCandidate(null)
  }

  // 开始预览候选视频
  const startPreview = (lineId: string, candidateId: string) => {
    setPreviewingCandidate({ lineId, candidateId })
  }

  // 关闭预览
  const closePreview = () => {
    setPreviewingCandidate(null)
  }

  // 获取当前选中的候选 ID（可能是已确认的或用户刚选择的）
  const getSelectedCandidateId = (line: typeof candidateLines[0]): string | null => {
    if (line.selected_segment_id) return line.selected_segment_id
    if (line.candidates.length > 0) return line.candidates[0].id
    return null
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
          to="/"
          className="inline-flex items-center gap-2 text-white/80 hover:text-white mb-8 active:scale-95 transition-all"
        >
          <ArrowLeft className="w-4 h-4" />
          返回主页
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
                <div className="flex items-center justify-between">
                  <p className="text-yellow-800 text-sm">
                    请检查以下歌词是否正确。如有错误，点击歌词进行编辑。确认无误后点击下方按钮开始匹配视频。
                  </p>
                  {!isSelectMode ? (
                    <button
                      onClick={() => setIsSelectMode(true)}
                      className="ml-4 px-3 py-1.5 text-sm text-red-600 border border-red-300 rounded-lg hover:bg-red-50 active:scale-95 active:bg-red-100 transition-all flex-shrink-0"
                    >
                      批量删除
                    </button>
                  ) : (
                    <div className="ml-4 flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={toggleSelectAll}
                        className="px-3 py-1.5 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 active:scale-95 active:bg-gray-100 transition-all"
                      >
                        {selectedLineIds.size === lyricsLines.length ? '取消全选' : '全选'}
                      </button>
                      <button
                        onClick={handleBatchDelete}
                        disabled={selectedLineIds.size === 0 || deleteLinesBatchMutation.isPending}
                        className="px-3 py-1.5 text-sm text-white bg-red-500 rounded-lg hover:bg-red-600 active:scale-95 active:bg-red-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                      >
                        {deleteLinesBatchMutation.isPending ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                        删除 ({selectedLineIds.size})
                      </button>
                      <button
                        onClick={exitSelectMode}
                        className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700 active:scale-95 transition-all"
                      >
                        取消
                      </button>
                    </div>
                  )}
                </div>
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
                      className={`p-4 flex items-center gap-4 hover:bg-gray-50 transition-colors ${
                        isSelectMode && selectedLineIds.has(line.id) ? 'bg-red-50' : ''
                      }`}
                    >
                      {/* 多选模式下显示复选框 */}
                      {isSelectMode ? (
                        <button
                          onClick={() => toggleLineSelection(line.id)}
                          className="flex-shrink-0 w-8 h-8 flex items-center justify-center active:scale-90 transition-transform"
                        >
                          <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                            selectedLineIds.has(line.id)
                              ? 'bg-red-500 border-red-500'
                              : 'border-gray-300 hover:border-red-400'
                          }`}>
                            {selectedLineIds.has(line.id) && (
                              <Check className="w-3 h-3 text-white" />
                            )}
                          </div>
                        </button>
                      ) : (
                        <div className="flex-shrink-0 w-8 h-8 flex items-center justify-center bg-purple-100 text-purple-600 rounded-full text-sm font-medium">
                          {line.line_no}
                        </div>
                      )}
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
                              className="p-1.5 text-green-600 hover:bg-green-50 active:scale-90 active:bg-green-100 rounded transition-all"
                            >
                              <Check className="w-5 h-5" />
                            </button>
                            <button
                              onClick={cancelEdit}
                              className="p-1.5 text-gray-400 hover:bg-gray-50 active:scale-90 active:bg-gray-100 rounded transition-all"
                            >
                              <X className="w-5 h-5" />
                            </button>
                          </div>
                        ) : (
                          <div
                            className={`group flex items-center gap-2 ${!isSelectMode ? 'cursor-pointer' : ''}`}
                            onClick={() => {
                              if (isSelectMode) {
                                toggleLineSelection(line.id)
                              } else {
                                startEdit(line.id, line.original_text)
                              }
                            }}
                          >
                            <p className="text-gray-900">{line.original_text}</p>
                            {!isSelectMode && (
                              <Edit3 className="w-4 h-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                            )}
                          </div>
                        )}
                        <p className="text-xs text-gray-500 mt-1">
                          {(line.start_time_ms / 1000).toFixed(1)}s - {(line.end_time_ms / 1000).toFixed(1)}s
                        </p>
                      </div>
                      {/* 非多选模式下显示删除按钮 */}
                      {!isSelectMode && (
                        <button
                          onClick={() => handleDeleteLine(line.id, line.original_text)}
                          disabled={deleteLineMutation.isPending}
                          className="flex-shrink-0 p-2 text-red-400 hover:text-red-600 hover:bg-red-50 active:scale-90 active:bg-red-100 rounded-lg transition-all disabled:opacity-50"
                          title="删除此行"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
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
                        className="px-4 py-2 text-gray-600 hover:bg-gray-100 active:scale-95 active:bg-gray-200 rounded-lg transition-all"
                      >
                        取消
                      </button>
                      <button
                        onClick={handleAddLine}
                        disabled={addLineMutation.isPending}
                        className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 active:scale-95 active:bg-purple-800 disabled:opacity-50 disabled:active:scale-100 flex items-center gap-2 transition-all"
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
                    className="w-full flex items-center justify-center gap-2 py-2 border-2 border-dashed border-purple-300 text-purple-600 rounded-lg hover:bg-purple-50 hover:border-purple-400 active:scale-[0.98] active:bg-purple-100 transition-all"
                  >
                    <Plus className="w-5 h-5" />
                    添加歌词
                  </button>
                )}
              </div>

              <div className="p-6 bg-gray-50">
                <button
                  onClick={handleConfirmAndMatch}
                  disabled={confirmLyricsMutation.isPending || matchVideosMutation.isPending || lyricsLines.length === 0 || isSelectMode}
                  className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white py-3 rounded-xl font-semibold hover:from-purple-700 hover:to-indigo-700 active:scale-[0.98] active:from-purple-800 active:to-indigo-800 disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100 transition-all"
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
              {/* 顶部提示和返回编辑按钮 */}
              <div className="p-4 bg-green-50 border-b border-green-100">
                <div className="flex items-center justify-between">
                  <p className="text-green-800 text-sm">
                    点击歌词可编辑，编辑后点击「重新匹配」获取新的候选视频，确认后可生成。
                  </p>
                  <button
                    onClick={() => {
                      if (confirm('返回将清除已匹配的视频，确定要返回修改歌词吗？')) {
                        unconfirmLyricsMutation.mutate()
                      }
                    }}
                    disabled={unconfirmLyricsMutation.isPending}
                    className="ml-4 px-3 py-1.5 text-sm text-orange-600 border border-orange-300 rounded-lg hover:bg-orange-50 active:scale-95 active:bg-orange-100 transition-all flex-shrink-0 flex items-center gap-1"
                  >
                    {unconfirmLyricsMutation.isPending ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ArrowLeft className="w-4 h-4" />
                    )}
                    返回修改歌词
                  </button>
                </div>
              </div>

              {/* Fallback 统计提示 */}
              {candidateLines.filter(l => l.candidates.length === 0).length > 0 && (
                <div className="p-3 bg-orange-50 border-b border-orange-100 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-orange-500 flex-shrink-0" />
                  <p className="text-orange-700 text-sm">
                    有 <span className="font-semibold">{candidateLines.filter(l => l.candidates.length === 0).length}</span> 句歌词未匹配到视频，将使用默认视频
                  </p>
                </div>
              )}

              <div className="divide-y divide-gray-100 max-h-[500px] overflow-y-auto">
                {candidateLines.length === 0 ? (
                  <div className="p-8 text-center text-gray-500">
                    <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2" />
                    正在加载...
                  </div>
                ) : (
                  candidateLines.map((line) => {
                    const isExpanded = expandedLineIds.has(line.id)
                    const selectedId = getSelectedCandidateId(line)

                    return (
                      <div
                        key={line.id}
                        className={`${line.candidates.length === 0 ? 'bg-orange-50/50' : ''}`}
                      >
                        {/* 歌词行主体 */}
                        <div className="p-4 flex items-center gap-4 hover:bg-gray-50 transition-colors">
                          {/* 左侧：状态图标 */}
                          <div className="flex-shrink-0">
                            {line.status === 'locked' ? (
                              <CheckCircle className="w-5 h-5 text-green-500" />
                            ) : line.candidates.length > 0 ? (
                              <div className="w-5 h-5 border-2 border-purple-400 rounded-full" />
                            ) : (
                              <span title="使用默认视频">
                                <AlertCircle className="w-5 h-5 text-orange-500" />
                              </span>
                            )}
                          </div>

                          {/* 中间：歌词内容（可编辑） */}
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
                                  className="p-1.5 text-green-600 hover:bg-green-50 active:scale-90 active:bg-green-100 rounded transition-all"
                                >
                                  <Check className="w-5 h-5" />
                                </button>
                                <button
                                  onClick={cancelEdit}
                                  className="p-1.5 text-gray-400 hover:bg-gray-50 active:scale-90 active:bg-gray-100 rounded transition-all"
                                >
                                  <X className="w-5 h-5" />
                                </button>
                              </div>
                            ) : (
                              <div
                                className="group flex items-center gap-2 cursor-pointer"
                                onClick={() => startEdit(line.id, line.original_text)}
                              >
                                <p className="text-gray-900">{line.original_text}</p>
                                <Edit3 className="w-4 h-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                                {line.candidates.length === 0 && (
                                  <span className="flex-shrink-0 px-2 py-0.5 text-xs font-medium bg-orange-100 text-orange-700 rounded">
                                    未匹配
                                  </span>
                                )}
                              </div>
                            )}
                            <p className="text-xs text-gray-500 mt-1">
                              {(line.start_time_ms / 1000).toFixed(1)}s - {(line.end_time_ms / 1000).toFixed(1)}s
                              {line.candidates.length > 0
                                ? ` | ${line.candidates.length} 个候选`
                                : ' | 将使用默认视频'}
                            </p>
                            {/* 搜索词：直接显示在歌词下方 */}
                            {line.candidates.length > 0 && line.candidates[0].search_query && (
                              <p className="text-xs text-blue-600 mt-1 bg-blue-50 px-2 py-1 rounded inline-block" title={line.candidates[0].search_query}>
                                🔍 {line.candidates[0].search_query.length > 60 ? line.candidates[0].search_query.slice(0, 60) + '...' : line.candidates[0].search_query}
                              </p>
                            )}
                          </div>

                          {/* 右侧：展开候选按钮和确认按钮 */}
                          <div className="flex items-center gap-2 flex-shrink-0">
                            {line.candidates.length > 0 && (
                              <button
                                onClick={() => toggleLineExpansion(line.id)}
                                className="p-2 text-gray-500 hover:bg-gray-100 active:scale-90 rounded-lg transition-all flex items-center gap-1"
                                title={isExpanded ? '收起候选' : '展开候选'}
                              >
                                <Video className="w-4 h-4" />
                                {isExpanded ? (
                                  <ChevronUp className="w-4 h-4" />
                                ) : (
                                  <ChevronDown className="w-4 h-4" />
                                )}
                              </button>
                            )}
                            {line.status !== 'locked' && line.candidates.length > 0 && (
                              <button
                                onClick={() => handleLockOne(line.id, selectedId!)}
                                disabled={lockMutation.isPending}
                                className="px-3 py-1 text-sm bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 active:scale-95 active:bg-purple-300 disabled:opacity-50 disabled:active:scale-100 transition-all"
                              >
                                {lockMutation.isPending ? '...' : '确认'}
                              </button>
                            )}
                          </div>
                        </div>

                        {/* 展开的候选列表 */}
                        {isExpanded && line.candidates.length > 0 && (
                          <div className="px-4 pb-4 pl-14 bg-gray-50">
                            <div className="text-xs text-gray-500 mb-2">选择视频片段：</div>
                            <div className="space-y-2">
                              {line.candidates.map((candidate, idx) => {
                                const isSelected = candidate.id === selectedId
                                const isPreviewing = previewingCandidate?.lineId === line.id && previewingCandidate?.candidateId === candidate.id

                                return (
                                  <div
                                    key={candidate.id}
                                    className={`p-3 rounded-lg border transition-all ${
                                      isSelected
                                        ? 'border-purple-400 bg-purple-50'
                                        : 'border-gray-200 bg-white hover:border-gray-300'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <div className="flex items-center gap-3">
                                        <span className={`w-6 h-6 flex items-center justify-center rounded-full text-xs font-medium ${
                                          isSelected ? 'bg-purple-600 text-white' : 'bg-gray-200 text-gray-600'
                                        }`}>
                                          {idx + 1}
                                        </span>
                                        <div>
                                          <p className="text-sm text-gray-700">
                                            视频片段 {(candidate.start_time_ms / 1000).toFixed(1)}s - {(candidate.end_time_ms / 1000).toFixed(1)}s
                                          </p>
                                          <p className="text-xs text-gray-400">
                                            评分: {candidate.score.toFixed(2)} | ID: {candidate.source_video_id.slice(0, 8)}...
                                          </p>
                                        </div>
                                      </div>
                                      <div className="flex items-center gap-2">
                                        <button
                                          onClick={() => startPreview(line.id, candidate.id)}
                                          className="px-2 py-1 text-xs text-blue-600 border border-blue-300 rounded hover:bg-blue-50 active:scale-95 transition-all"
                                        >
                                          <Play className="w-3 h-3 inline mr-1" />
                                          预览
                                        </button>
                                        {!isSelected && (
                                          <button
                                            onClick={() => handleSelectCandidate(line.id, candidate.id)}
                                            className="px-2 py-1 text-xs text-purple-600 border border-purple-300 rounded hover:bg-purple-50 active:scale-95 transition-all"
                                          >
                                            选择
                                          </button>
                                        )}
                                        {isSelected && (
                                          <span className="px-2 py-1 text-xs text-green-600 bg-green-100 rounded">
                                            已选
                                          </span>
                                        )}
                                      </div>
                                    </div>

                                    {/* 视频预览 */}
                                    {isPreviewing && (
                                      <div className="mt-3 relative">
                                        <video
                                          src={getCandidatePreviewUrl(mixId!, line.id, candidate.id)}
                                          controls
                                          autoPlay
                                          className="w-full rounded-lg max-h-48 bg-black"
                                          onError={() => alert('视频预览加载失败')}
                                        />
                                        <button
                                          onClick={closePreview}
                                          className="absolute top-2 right-2 p-1 bg-black/50 text-white rounded-full hover:bg-black/70"
                                        >
                                          <X className="w-4 h-4" />
                                        </button>
                                      </div>
                                    )}
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })
                )}
              </div>

              {/* 渲染选项 */}
              <div className="p-4 border-t border-gray-100 bg-white">
                <label className="flex items-center gap-3 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={bilingualSubtitle}
                    onChange={(e) => setBilingualSubtitle(e.target.checked)}
                    className="w-5 h-5 rounded border-gray-300 text-purple-600 focus:ring-purple-500 cursor-pointer"
                  />
                  <div>
                    <span className="text-gray-900 font-medium">中英双语字幕</span>
                    <p className="text-xs text-gray-500">英文歌词将自动翻译为中文，显示双语字幕</p>
                  </div>
                </label>
              </div>

              {/* Actions */}
              <div className="p-6 bg-gray-50 flex items-center gap-4">
                <button
                  onClick={() => matchVideosMutation.mutate()}
                  disabled={matchVideosMutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 border border-purple-300 text-purple-700 rounded-lg hover:bg-purple-50 active:scale-95 active:bg-purple-100 disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100 transition-all"
                >
                  <RefreshCw className={`w-4 h-4 ${matchVideosMutation.isPending ? 'animate-spin' : ''}`} />
                  重新匹配
                </button>
                <button
                  onClick={handleLockAll}
                  disabled={allLocked || lockMutation.isPending}
                  className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-white active:scale-95 active:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100 transition-all"
                >
                  <RefreshCw className={`w-4 h-4 ${lockMutation.isPending ? 'animate-spin' : ''}`} />
                  全部确认
                </button>
                <button
                  onClick={() => renderMutation.mutate()}
                  disabled={!allLocked || renderMutation.isPending}
                  className="flex-1 flex items-center justify-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white py-3 rounded-xl font-semibold hover:from-purple-700 hover:to-indigo-700 active:scale-[0.98] active:from-purple-800 active:to-indigo-800 disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100 transition-all"
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
