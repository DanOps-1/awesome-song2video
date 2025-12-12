import { useState, useRef, useCallback } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Music, Upload, ArrowLeft, Loader2, X, FileAudio, Monitor, Smartphone, Square, Tv } from 'lucide-react'
import { createMix, transcribeLyrics, fetchLyrics, uploadAudio } from '@/api/mix'

export default function Create() {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [formData, setFormData] = useState({
    song_title: '',
    artist: '',
    language: 'auto',
    lyricsMode: 'search' as 'search' | 'ai',  // search=搜索歌词(推荐), ai=AI识别
    aspect_ratio: '9:16' as '16:9' | '9:16' | '1:1' | '4:3',  // 默认竖屏（短视频主流）
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
      if (!audioFile) throw new Error('请上传音频文件')

      // 上传音频文件
      const uploadResult = await uploadAudio(audioFile)

      // 创建混剪任务
      const createPayload = {
        song_title: formData.song_title,
        artist: formData.artist || undefined,
        source_type: 'upload',
        audio_asset_id: uploadResult.id,
        language: formData.language,
        aspect_ratio: formData.aspect_ratio,
      }
      console.log('Creating mix with payload:', createPayload)
      const mix = await createMix(createPayload)

      // 根据用户选择的模式获取歌词
      if (formData.lyricsMode === 'search') {
        // 搜索模式：优先从音乐平台获取歌词，失败则回退到 AI 识别
        fetchLyrics(mix.id)
          .then((result) => {
            console.log('歌词获取成功:', result.matched_song, result.line_count + '句')
          })
          .catch((err) => {
            console.log('歌词搜索失败，回退到 AI 识别:', err.message)
            transcribeLyrics(mix.id).catch(console.error)
          })
      } else {
        // AI 识别模式：直接使用 Whisper 识别
        transcribeLyrics(mix.id).catch(console.error)
      }

      return mix
    },
    onSuccess: (mix) => {
      navigate(`/status/${mix.id}`)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.song_title || !audioFile) return
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
            {/* 音频上传区域 */}
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
                <option value="auto">自动检测</option>
                <option value="zh">中文</option>
                <option value="en">英文</option>
              </select>
            </div>

            {/* 视频比例选择 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                视频比例
              </label>
              <div className="grid grid-cols-4 gap-3">
                {[
                  { value: '9:16', label: '9:16', desc: '竖屏', icon: Smartphone, platform: '抖音/快手' },
                  { value: '16:9', label: '16:9', desc: '横屏', icon: Monitor, platform: 'B站/YouTube' },
                  { value: '1:1', label: '1:1', desc: '方形', icon: Square, platform: '微信/Instagram' },
                  { value: '4:3', label: '4:3', desc: '传统', icon: Tv, platform: '经典比例' },
                ].map((ratio) => (
                  <label
                    key={ratio.value}
                    className={`
                      relative flex flex-col items-center p-3 border-2 rounded-xl cursor-pointer transition-all
                      ${formData.aspect_ratio === ratio.value
                        ? 'border-purple-500 bg-purple-50'
                        : 'border-gray-200 hover:border-purple-300 hover:bg-gray-50'
                      }
                    `}
                  >
                    <input
                      type="radio"
                      name="aspect_ratio"
                      value={ratio.value}
                      checked={formData.aspect_ratio === ratio.value}
                      onChange={(e) => setFormData(prev => ({ ...prev, aspect_ratio: e.target.value as '16:9' | '9:16' | '1:1' | '4:3' }))}
                      className="sr-only"
                    />
                    <ratio.icon className={`w-6 h-6 mb-1 ${formData.aspect_ratio === ratio.value ? 'text-purple-600' : 'text-gray-400'}`} />
                    <span className={`font-medium text-sm ${formData.aspect_ratio === ratio.value ? 'text-purple-700' : 'text-gray-700'}`}>
                      {ratio.label}
                    </span>
                    <span className="text-xs text-gray-500">{ratio.desc}</span>
                    <span className="text-xs text-gray-400 mt-0.5">{ratio.platform}</span>
                    {ratio.value === '9:16' && (
                      <span className="absolute -top-2 -right-2 px-1.5 py-0.5 text-xs bg-green-500 text-white rounded-full">
                        热门
                      </span>
                    )}
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                歌词获取方式
              </label>
              <div className="space-y-2">
                <label className="flex items-start gap-3 p-3 border border-gray-200 rounded-xl cursor-pointer hover:bg-gray-50 transition-colors has-[:checked]:border-purple-500 has-[:checked]:bg-purple-50">
                  <input
                    type="radio"
                    name="lyricsMode"
                    value="search"
                    checked={formData.lyricsMode === 'search'}
                    onChange={(e) => setFormData(prev => ({ ...prev, lyricsMode: e.target.value as 'search' | 'ai' }))}
                    className="mt-1 text-purple-600 focus:ring-purple-500"
                  />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900">在线搜索歌词</span>
                      <span className="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded-full">推荐</span>
                    </div>
                    <p className="text-sm text-gray-500 mt-0.5">
                      从 QQ音乐、网易云、酷狗等平台搜索精准歌词，速度快、准确率高
                    </p>
                  </div>
                </label>
                <label className="flex items-start gap-3 p-3 border border-gray-200 rounded-xl cursor-pointer hover:bg-gray-50 transition-colors has-[:checked]:border-purple-500 has-[:checked]:bg-purple-50">
                  <input
                    type="radio"
                    name="lyricsMode"
                    value="ai"
                    checked={formData.lyricsMode === 'ai'}
                    onChange={(e) => setFormData(prev => ({ ...prev, lyricsMode: e.target.value as 'search' | 'ai' }))}
                    className="mt-1 text-purple-600 focus:ring-purple-500"
                  />
                  <div className="flex-1">
                    <span className="font-medium text-gray-900">AI 语音识别</span>
                    <p className="text-sm text-gray-500 mt-0.5">
                      使用 Whisper 识别音频中的歌词，适合冷门歌曲或自创内容
                    </p>
                  </div>
                </label>
              </div>
            </div>

            <button
              type="submit"
              disabled={createMutation.isPending || !formData.song_title || !audioFile}
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
                创建失败：{(createMutation.error as Error)?.message || '请重试'}
              </p>
            )}
          </form>
        </div>
      </div>
    </div>
  )
}
