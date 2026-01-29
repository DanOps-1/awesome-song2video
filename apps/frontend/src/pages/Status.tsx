import { useParams, Link, useNavigate, Navigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { useState } from 'react'
import { 
  Button, 
  Input, 
  message,
  Spin,
  Tag,
  Checkbox
} from 'antd'
import { 
  ArrowLeftOutlined, 
  CheckCircleFilled, 
  PlayCircleFilled, 
  DeleteOutlined, 
  PlusOutlined,
  EditOutlined,
  SaveOutlined,
  CloseOutlined,
  ReloadOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons'
import { motion, AnimatePresence } from 'framer-motion'
import {
  getLines,
  submitRender,
  lockLine,
  lockAllLines,
  getMixStatus,
  updateLine,
  confirmLyrics,
  matchVideos,
  deleteLine,
  addLine,
  getCandidatePreviewUrl,
  type LineInfo,
  type CandidateInfo,
  type AddLineRequest
} from '@/api/mix'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.05 } }
}

const itemVariants = {
  hidden: { opacity: 0, x: -10 },
  visible: { opacity: 1, x: 0 }
}

export default function Status() {
  const { mixId } = useParams<{ mixId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [messageApi, contextHolder] = message.useMessage()

  if (!mixId) {
    return <Navigate to="/" replace />
  }

  const [editingLineId, setEditingLineId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [showAddForm, setShowAddForm] = useState(false)
  const [newLyricText, setNewLyricText] = useState('')
  const [newLyricStartSec, setNewLyricStartSec] = useState('')
  const [newLyricEndSec, setNewLyricEndSec] = useState('')
  const [previewingCandidate, setPreviewingCandidate] = useState<{lineId: string, candidateId: string} | null>(null)
  const [bilingualSubtitle, setBilingualSubtitle] = useState(false)

  const { data: mixData, isLoading: mixLoading } = useQuery({
    queryKey: ['mix', mixId],
    queryFn: () => getMixStatus(mixId),
    enabled: !!mixId,
    refetchInterval: (query) => {
      const status = query.state.data?.timeline_status
      return (!status || ['pending', 'transcribing', 'matching'].includes(status)) ? 2000 : false
    },
  })

  const { data: linesData } = useQuery({
    queryKey: ['lines', mixId],
    queryFn: () => getLines(mixId),
    enabled: !!mixId && mixData?.timeline_status === 'generated',
    placeholderData: keepPreviousData,
  })

  // --- Mutations (Simplified for brevity, same logic) ---
  const updateLineMutation = useMutation({
    mutationFn: ({ lineId, text }: { lineId: string; text: string }) => updateLine(mixId, lineId, text),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['mix', mixId] }); setEditingLineId(null); messageApi.success('已更新'); }
  })
  const deleteLineMutation = useMutation({
    mutationFn: (lineId: string) => deleteLine(mixId, lineId),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['mix', mixId] }); messageApi.success('已删除'); }
  })
  const addLineMutation = useMutation({
    mutationFn: (payload: AddLineRequest) => addLine(mixId, payload),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['mix', mixId] }); setShowAddForm(false); messageApi.success('已添加'); }
  })
  const confirmLyricsMutation = useMutation({
    mutationFn: () => confirmLyrics(mixId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['mix', mixId] })
  })
  const matchVideosMutation = useMutation({
    mutationFn: () => matchVideos(mixId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['mix', mixId] })
  })
  const lockMutation = useMutation({
    mutationFn: ({ lineId, segmentId }: { lineId: string; segmentId: string }) => lockLine(mixId, lineId, segmentId),
    onSuccess: () => setTimeout(() => queryClient.invalidateQueries({ queryKey: ['lines', mixId] }), 100)
  })
  const lockAllMutation = useMutation({
    mutationFn: () => lockAllLines(mixId, candidateLines),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['lines', mixId] }); messageApi.success('已全部确认'); }
  })
  const renderMutation = useMutation({
    mutationFn: () => submitRender(mixId, { bilingual_subtitle: bilingualSubtitle }),
    onSuccess: (data) => { sessionStorage.setItem(`job_${mixId}`, data.job_id); navigate(`/result/${mixId}`); }
  })

  const timelineStatus = mixData?.timeline_status ?? 'pending'
  const timelineProgress = mixData?.timeline_progress ?? 0
  const lyricsLines = mixData?.lines ?? []
  const candidateLines = linesData?.lines ?? []

  // --- Helpers ---
  const handleAddLine = () => {
    const s = parseFloat(newLyricStartSec) * 1000, e = parseFloat(newLyricEndSec) * 1000
    if (!newLyricText || isNaN(s) || isNaN(e) || e <= s) return messageApi.warning('请输入有效的歌词和时间')
    addLineMutation.mutate({ text: newLyricText, start_time_ms: s, end_time_ms: e })
  }

  if (mixLoading) return <div className="h-screen flex items-center justify-center"><Spin size="large" tip="加载中..." /></div>
  
  return (
    <div className="w-full max-w-5xl mx-auto px-4 py-8 pr-6">
      {contextHolder}
      <div className="flex items-center justify-between mb-8">
        <Link to="/" className="text-white/50 hover:text-white transition-colors flex items-center gap-2">
          <ArrowLeftOutlined /> 返回首页
        </Link>
        <div className="flex items-center gap-3">
          <span className="text-white/60 text-sm">任务 ID: {mixId?.slice(0, 8)}</span>
          <Tag color={timelineStatus === 'error' ? 'red' : 'purple'}>{timelineStatus.toUpperCase()}</Tag>
        </div>
      </div>

      {/* Progress Section */}
      <div className="glass rounded-3xl p-8 mb-8 relative overflow-hidden">
        <div className="flex items-center justify-between mb-6 relative z-10">
          <div>
            <h2 className="text-2xl font-bold text-white mb-1">
              {timelineStatus === 'transcribing' ? '正在识别歌词' :
               timelineStatus === 'transcribed' ? '歌词校对' :
               timelineStatus === 'matching' ? '正在匹配视频' :
               timelineStatus === 'generated' ? '混剪预览' : '准备中'}
            </h2>
            <p className="text-white/50">
               {timelineStatus === 'transcribing' ? 'AI 正在聆听音频内容...' :
               timelineStatus === 'transcribed' ? '请确认歌词准确无误' :
               timelineStatus === 'matching' ? '正在全网搜索最佳画面...' :
               '选择最合适的视频片段'}
            </p>
          </div>
          {(timelineStatus === 'transcribing' || timelineStatus === 'matching') && (
            <div className="text-right">
              <span className="text-4xl font-bold text-violet-400">{Math.round(timelineProgress)}%</span>
            </div>
          )}
        </div>
        
        {/* Animated Progress Bar */}
        {(timelineStatus === 'transcribing' || timelineStatus === 'matching') && (
           <div className="h-2 bg-white/10 rounded-full overflow-hidden relative z-10">
             <motion.div 
               className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500"
               initial={{ width: 0 }}
               animate={{ width: `${timelineProgress}%` }}
               transition={{ type: 'spring', damping: 20 }}
             />
           </div>
        )}
      </div>

      {/* Main Content Area */}
      <AnimatePresence mode="wait">
        {timelineStatus === 'transcribed' && (
          <motion.div 
            key="lyrics-editor"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="glass rounded-3xl p-6 md:p-8"
          >
            <div className="flex justify-end gap-3 mb-6">
              <Button 
                type={showAddForm ? 'primary' : 'default'} 
                icon={showAddForm ? <CloseOutlined /> : <PlusOutlined />}
                onClick={() => setShowAddForm(!showAddForm)}
                ghost={!showAddForm}
              >
                {showAddForm ? '取消添加' : '添加歌词'}
              </Button>
              <Button 
                 type="primary" 
                 onClick={() => { confirmLyricsMutation.mutate(); matchVideosMutation.mutate(); }}
                 loading={confirmLyricsMutation.isPending || matchVideosMutation.isPending}
                 className="bg-gradient-to-r from-violet-600 to-fuchsia-600 border-none hover:shadow-lg hover:shadow-violet-500/20"
              >
                确认并匹配视频
              </Button>
            </div>

            {/* Add Form */}
            <AnimatePresence>
              {showAddForm && (
                <motion.div 
                  initial={{ height: 0, opacity: 0 }} 
                  animate={{ height: 'auto', opacity: 1 }} 
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden mb-6 bg-white/5 rounded-xl border border-white/10"
                >
                  <div className="p-4 grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
                    <Input placeholder="歌词内容" className="md:col-span-2 glass-input" value={newLyricText} onChange={e => setNewLyricText(e.target.value)} />
                    <Input placeholder="开始(秒)" className="glass-input" value={newLyricStartSec} onChange={e => setNewLyricStartSec(e.target.value)} />
                    <div className="flex gap-2">
                       <Input placeholder="结束(秒)" className="glass-input" value={newLyricEndSec} onChange={e => setNewLyricEndSec(e.target.value)} />
                       <Button type="primary" onClick={handleAddLine} loading={addLineMutation.isPending}>ok</Button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <motion.div variants={containerVariants} initial="hidden" animate="visible" className="space-y-3 max-h-[60vh] overflow-y-auto pr-2 custom-scrollbar">
              {lyricsLines.map((line: LineInfo) => (
                <motion.div 
                  key={line.id} 
                  variants={itemVariants}
                  className="group bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/20 rounded-xl p-4 transition-all flex items-center gap-4"
                >
                  <div className="w-8 h-8 rounded-full bg-violet-500/20 text-violet-300 flex items-center justify-center text-sm font-bold">
                    {line.line_no}
                  </div>
                  
                  <div className="flex-1">
                    {editingLineId === line.id ? (
                      <div className="flex items-center gap-2">
                        <Input 
                          value={editText} 
                          onChange={e => setEditText(e.target.value)} 
                          className="glass-input"
                          autoFocus
                          onPressEnter={() => updateLineMutation.mutate({ lineId: line.id, text: editText })}
                        />
                        <Button type="text" icon={<SaveOutlined className="text-green-400" />} onClick={() => updateLineMutation.mutate({ lineId: line.id, text: editText })} />
                        <Button type="text" icon={<CloseOutlined className="text-gray-400" />} onClick={() => setEditingLineId(null)} />
                      </div>
                    ) : (
                      <div className="flex items-center justify-between cursor-pointer" onClick={() => { setEditingLineId(line.id); setEditText(line.original_text); }}>
                         <div>
                           <p className="text-white font-medium text-lg">{line.original_text}</p>
                           <p className="text-white/40 text-xs">{(line.start_time_ms/1000).toFixed(1)}s - {(line.end_time_ms/1000).toFixed(1)}s</p>
                         </div>
                         <EditOutlined className="text-white/20 group-hover:text-white/60 transition-colors" />
                      </div>
                    )}
                  </div>
                  
                  <Button 
                    type="text" 
                    danger 
                    icon={<DeleteOutlined />} 
                    className="opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={() => deleteLineMutation.mutate(line.id)}
                  />
                </motion.div>
              ))}
            </motion.div>
          </motion.div>
        )}

        {timelineStatus === 'generated' && (
          <motion.div 
            key="video-matcher"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-6"
          >
            {/* Toolbar */}
            <div className="glass rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4 sticky top-4 z-20 backdrop-blur-xl">
               <div className="flex items-center gap-4">
                  <span className="text-white/70">已确认: <span className="text-violet-400 font-bold">{candidateLines.filter((l: LineInfo) => l.status === 'locked').length}</span> / {candidateLines.length}</span>
                  <Checkbox
                    checked={bilingualSubtitle}
                    onChange={e => setBilingualSubtitle(e.target.checked)}
                    className="text-white/80"
                  >
                    双语字幕
                  </Checkbox>
               </div>
               <div className="flex gap-3">
                  <Button
                    icon={<ReloadOutlined />}
                    onClick={() => matchVideosMutation.mutate()}
                    loading={matchVideosMutation.isPending}
                    className="border-orange-500 text-orange-400 hover:bg-orange-500/10"
                  >
                    重试匹配
                  </Button>
                  <Button
                    icon={<CheckCircleFilled />}
                    onClick={() => lockAllMutation.mutate()}
                    loading={lockAllMutation.isPending}
                    disabled={candidateLines.every((l: LineInfo) => l.status === 'locked')}
                    className="border-green-500 text-green-400 hover:bg-green-500/10"
                  >
                    全部确认
                  </Button>
                  <Button
                    type="primary"
                    icon={<PlayCircleFilled />}
                    onClick={() => renderMutation.mutate()}
                    loading={renderMutation.isPending}
                    disabled={candidateLines.some((l: LineInfo) => l.status !== 'locked')}
                    className="bg-gradient-to-r from-violet-600 to-fuchsia-600 border-none"
                  >
                    生成视频
                  </Button>
               </div>
            </div>

            <div className="space-y-6">
               {candidateLines.map((line: LineInfo) => {
                 const isLocked = line.status === 'locked'
                 const selectedCand = line.candidates.find((c: CandidateInfo) => c.id === (line.selected_segment_id || line.candidates[0]?.id))
                 
                 return (
                   <div key={line.id} className={`glass rounded-2xl p-6 transition-all border ${isLocked ? 'border-green-500/30 bg-green-500/5' : 'border-white/10'}`}>
                      <div className="flex flex-col md:flex-row gap-6">
                         {/* Lyric Info */}
                         <div className="md:w-1/3 flex flex-col justify-center">
                            <h3 className="text-xl font-bold text-white mb-2">{line.original_text}</h3>
                            <div className="flex items-center gap-2 mb-4">
                               <Tag color="blue">{(line.start_time_ms/1000).toFixed(1)}s</Tag>
                               <span className="text-white/30">to</span>
                               <Tag color="blue">{(line.end_time_ms/1000).toFixed(1)}s</Tag>
                            </div>
                            <div className="text-white/50 text-sm">
                               关键词: {line.candidates[0]?.search_query || 'N/A'}
                            </div>
                         </div>

                         {/* Candidates Gallery */}
                         <div className="md:w-2/3 overflow-x-auto pb-4 custom-scrollbar flex gap-4">
                            {line.candidates.length === 0 ? (
                               <div className="w-full h-32 flex items-center justify-center border border-dashed border-white/20 rounded-xl text-white/40">
                                  <ExclamationCircleOutlined className="mr-2" /> 无匹配视频
                               </div>
                             ) : (
                               line.candidates.map((cand: CandidateInfo) => {
                                  const isSelected = selectedCand?.id === cand.id
                                  return (
                                     <div  
                                        key={cand.id} 
                                        className={`relative flex-shrink-0 w-48 group cursor-pointer rounded-xl overflow-hidden border-2 transition-all ${isSelected ? 'border-violet-500 shadow-lg shadow-violet-500/20' : 'border-transparent opacity-60 hover:opacity-100'}`}
                                        onClick={() => lockMutation.mutate({ lineId: line.id, segmentId: cand.id })}
                                     >
                                        <div className="aspect-video bg-black relative">
                                           {previewingCandidate?.candidateId === cand.id ? (
                                              <video
                                                src={getCandidatePreviewUrl(mixId, line.id, cand.id)}
                                                autoPlay
                                                loop
                                                muted
                                                playsInline
                                                className="w-full h-full object-cover"
                                                onError={(e) => {
                                                  console.error('视频加载失败:', e);
                                                  setPreviewingCandidate(null);
                                                  messageApi.error('视频预览加载失败');
                                                }}
                                              />
                                           ) : (
                                              <div
                                                className="w-full h-full bg-gray-900 flex items-center justify-center cursor-pointer hover:bg-gray-800 transition-colors"
                                                onClick={(e) => {
                                                  e.stopPropagation();
                                                  setPreviewingCandidate({ lineId: line.id, candidateId: cand.id });
                                                }}
                                              >
                                                 <PlayCircleFilled className="text-3xl text-white/40 hover:text-white/80 transition-colors" />
                                              </div>
                                           )}

                                           {/* 播放中显示停止按钮 */}
                                           {previewingCandidate?.candidateId === cand.id && (
                                              <div
                                                className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity cursor-pointer"
                                                onClick={(e) => { e.stopPropagation(); setPreviewingCandidate(null); }}
                                              >
                                                 <div className="bg-black/60 rounded-full p-2">
                                                    <CloseOutlined className="text-white text-lg" />
                                                 </div>
                                              </div>
                                           )}
                                        </div>
                                        
                                        <div className="p-2 bg-gray-900/90 text-xs text-white/70 flex justify-between">
                                           <span>Score: {cand.score.toFixed(2)}</span>
                                           {isSelected && <CheckCircleFilled className="text-green-500" />}
                                        </div>
                                     </div>
                                  )
                               })
                            )}
                         </div>
                      </div>
                   </div>
                 )
               })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
