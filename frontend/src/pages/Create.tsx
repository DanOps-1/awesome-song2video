import { useState, useRef, useCallback } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Music, Upload, ArrowLeft, Loader2, X, FileAudio } from 'lucide-react'
import { createMix, transcribeLyrics, importLyrics, uploadAudio } from '@/api/mix'

type InputMode = 'audio' | 'manual'

export default function Create() {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [inputMode, setInputMode] = useState<InputMode>('audio')
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [formData, setFormData] = useState({
    song_title: '',
    artist: '',
    lyrics_text: '',
    language: 'zh',
  })

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const file = e.dataTransfer.files[0]
    if (file && isValidAudioFile(file)) {
      setAudioFile(file)
      // 自动填充歌曲名称
      if (!formData.song_title) {
        const name = file.name.replace(/\.[^/.]+$/, '')
        setFormData(prev => ({ ...prev, song_title: name }))
      }
    }
  }, [formData.song_title])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file && isValidAudioFile(file)) {
      setAudioFile(file)
      // 自动填充歌曲名称
      if (!formData.song_title) {
        const name = file.name.replace(/\.[^/.]+$/, '')
        setFormData(prev => ({ ...prev, song_title: name }))
      }
    }
  }

  const isValidAudioFile = (file: File) => {
    const validTypes = ['audio/mpeg', 'audio/wav', 'audio/flac', 'audio/mp4', 'audio/aac', 'audio/x-m4a']
    const validExtensions = ['.mp3', '.wav', '.flac', '.m4a', '.aac']
    const extension = file.name.toLowerCase().slice(file.name.lastIndexOf('.'))
    return validTypes.includes(file.type) || validExtensions.includes(extension)
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  const createMutation = useMutation({
    mutationFn: async () => {
      let audioAssetId: string | undefined

      // 音频模式：上传音频文件
      if (inputMode === 'audio' && audioFile) {
        const uploadResult = await uploadAudio(audioFile)
        audioAssetId = uploadResult.id
      }

      // 创建混剪任务
      const mix = await createMix({
        song_title: formData.song_title,
        artist: formData.artist || undefined,
        source_type: inputMode === 'audio' ? 'upload' : 'manual',
        audio_asset_id: audioAssetId,
        lyrics_text: formData.lyrics_text || undefined,
        language: formData.language,
      })

      if (inputMode === 'manual') {
        // 手动模式：直接导入带时间戳的歌词
        await importLyrics(mix.id, formData.lyrics_text)
      } else if (formData.lyrics_text && formData.lyrics_text.trim()) {
        // 音频模式 + 用户提供歌词：跳过 Whisper 识别
        await importLyrics(mix.id, formData.lyrics_text)
      } else {
        // 音频模式 + 无歌词：触发 Whisper 识别
        transcribeLyrics(mix.id).catch(console.error)
      }

      return mix
    },
    onSuccess: (mix) => {
      navigate(`/status/${mix.id}`)
    },
  })

  // 表单验证
  const isFormValid = () => {
    if (!formData.song_title) return false
    if (inputMode === 'audio') {
      return !!audioFile
    } else {
      return !!(formData.lyrics_text && formData.lyrics_text.trim())
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!isFormValid()) return
    createMutation.mutate()
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-2xl mx-auto">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-white/80 hover:text-white mb-8"
        >
          <ArrowLeft className="w-4 h-4" />
          返回首页
        </Link>

        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center">
              <Music className="w-6 h-6 text-purple-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">创建混剪</h1>
              <p className="text-gray-500">上传音频开始 AI 混剪</p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* 模式切换 */}
            <div className="flex gap-2 p-1 bg-gray-100 rounded-xl">
              <button
                type="button"
                onClick={() => setInputMode('audio')}
                className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
                  inputMode === 'audio'
                    ? 'bg-white text-purple-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                上传音频
              </button>
              <button
                type="button"
                onClick={() => setInputMode('manual')}
                className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
                  inputMode === 'manual'
                    ? 'bg-white text-purple-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                手动输入歌词
              </button>
            </div>

            {/* 音频模式：上传区域 */}
            {inputMode === 'audio' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  音频文件 <span className="text-red-500">*</span>
                </label>
                {!audioFile ? (
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    className={`
                      border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
                      ${isDragging
                        ? 'border-purple-500 bg-purple-50'
                        : 'border-gray-300 hover:border-purple-400 hover:bg-gray-50'
                      }
                    `}
                  >
                    <Upload className={`w-10 h-10 mx-auto mb-3 ${isDragging ? 'text-purple-500' : 'text-gray-400'}`} />
                    <p className="text-gray-600 mb-1">
                      拖拽音频文件到此处，或点击选择
                    </p>
                    <p className="text-xs text-gray-400">
                      支持 MP3、WAV、FLAC、M4A、AAC 格式
                    </p>
                  </div>
                ) : (
                  <div className="border border-gray-200 rounded-xl p-4 flex items-center gap-4">
                    <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center flex-shrink-0">
                      <FileAudio className="w-6 h-6 text-purple-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-gray-900 font-medium truncate">{audioFile.name}</p>
                      <p className="text-sm text-gray-500">{formatFileSize(audioFile.size)}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setAudioFile(null)}
                      className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".mp3,.wav,.flac,.m4a,.aac,audio/*"
                  onChange={handleFileSelect}
                  className="hidden"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                歌曲名称 <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={formData.song_title}
                onChange={(e) => setFormData(prev => ({ ...prev, song_title: e.target.value }))}
                placeholder="输入歌曲名称"
                className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                歌手
              </label>
              <input
                type="text"
                value={formData.artist}
                onChange={(e) => setFormData(prev => ({ ...prev, artist: e.target.value }))}
                placeholder="输入歌手名"
                className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                语言
              </label>
              <select
                value={formData.language}
                onChange={(e) => setFormData(prev => ({ ...prev, language: e.target.value }))}
                className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              >
                <option value="zh">中文</option>
                <option value="en">英文</option>
                <option value="auto">自动检测</option>
              </select>
            </div>

            {/* 歌词输入区域 - 根据模式显示不同内容 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {inputMode === 'manual' ? (
                  <>歌词 <span className="text-red-500">*</span></>
                ) : (
                  '歌词（可选，跳过 AI 识别）'
                )}
              </label>
              <textarea
                value={formData.lyrics_text}
                onChange={(e) => setFormData(prev => ({ ...prev, lyrics_text: e.target.value }))}
                placeholder={inputMode === 'manual'
                  ? `请输入歌词，每行一句，例如：
春风又绿江南岸
明月何时照我还
举头望明月
低头思故乡`
                  : '粘贴歌词，每行一句...'}
                rows={inputMode === 'manual' ? 10 : 6}
                className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
              />
              <p className="mt-1 text-xs text-gray-500">
                {inputMode === 'manual' ? (
                  '每行一句歌词，系统会根据歌词数量均匀分配时间'
                ) : (
                  formData.lyrics_text?.trim()
                    ? '✓ 将使用您提供的歌词，跳过 AI 识别'
                    : '如不提供，将自动从音频识别歌词（需要几分钟）'
                )}
              </p>
            </div>

            <button
              type="submit"
              disabled={createMutation.isPending || !isFormValid()}
              className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 text-white py-4 rounded-xl font-semibold text-lg hover:from-purple-700 hover:to-indigo-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {createMutation.isPending ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  创建中...
                </>
              ) : (
                <>
                  <Upload className="w-5 h-5" />
                  开始混剪
                </>
              )}
            </button>

            {createMutation.isError && (
              <p className="text-red-500 text-center">
                创建失败，请重试
              </p>
            )}
          </form>
        </div>
      </div>
    </div>
  )
}
