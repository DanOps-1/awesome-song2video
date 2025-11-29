import { Link } from 'react-router-dom'
import { Music, Sparkles, Play } from 'lucide-react'

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8">
      <div className="text-center mb-12">
        <div className="inline-flex items-center justify-center w-20 h-20 bg-white/20 rounded-full mb-6">
          <Music className="w-10 h-10 text-white" />
        </div>
        <h1 className="text-5xl font-bold text-white mb-4">Song2Video</h1>
        <p className="text-xl text-white/80 max-w-md mx-auto">
          AI 驱动的歌词语义混剪，让你的音乐拥有画面
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-3 max-w-4xl w-full">
        <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-6 text-center">
          <div className="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <Music className="w-6 h-6 text-white" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">上传音频</h3>
          <p className="text-white/70 text-sm">支持 MP3、WAV 等格式</p>
        </div>

        <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-6 text-center">
          <div className="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-6 h-6 text-white" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">AI 匹配</h3>
          <p className="text-white/70 text-sm">自动匹配歌词与视频片段</p>
        </div>

        <div className="bg-white/10 backdrop-blur-sm rounded-2xl p-6 text-center">
          <div className="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <Play className="w-6 h-6 text-white" />
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">导出视频</h3>
          <p className="text-white/70 text-sm">一键生成混剪视频</p>
        </div>
      </div>

      <Link
        to="/create"
        className="mt-12 inline-flex items-center gap-2 bg-white text-purple-600 px-8 py-4 rounded-full font-semibold text-lg hover:bg-white/90 transition-colors shadow-lg"
      >
        <Sparkles className="w-5 h-5" />
        开始创作
      </Link>
    </div>
  )
}
