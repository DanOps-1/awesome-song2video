import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Loader2, CheckCircle, Download, Home } from 'lucide-react'
import { getRenderStatus } from '@/api/mix'
import { useState, useEffect } from 'react'

export default function Result() {
  const { mixId } = useParams<{ mixId: string }>()
  const [jobId, setJobId] = useState<string | null>(null)

  // 首先获取 job_id
  useEffect(() => {
    const storedJobId = sessionStorage.getItem(`job_${mixId}`)
    if (storedJobId) {
      setJobId(storedJobId)
    }
  }, [mixId])

  const { data: renderData, isLoading } = useQuery({
    queryKey: ['render-status', mixId, jobId],
    queryFn: () => getRenderStatus(mixId!, jobId!),
    enabled: !!mixId && !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data
      if (data?.status === 'success' || data?.status === 'failed') {
        return false
      }
      return 2000  // 每2秒刷新一次以获取最新进度
    },
  })

  const isComplete = renderData?.status === 'success'
  const isFailed = renderData?.status === 'failed'
  const isProcessing = !isComplete && !isFailed

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="max-w-md w-full">
        <div className="bg-white rounded-2xl shadow-xl p-8 text-center">
          {isProcessing && (
            <>
              <Loader2 className="w-16 h-16 text-purple-600 animate-spin mx-auto mb-6" />
              <h1 className="text-2xl font-bold text-gray-900 mb-2">视频生成中</h1>
              <p className="text-gray-500 mb-4">
                正在渲染您的混剪视频，请稍候...
              </p>
              <div className="mb-2">
                <span className="text-2xl font-bold text-purple-600">
                  {(renderData?.progress ?? 0).toFixed(0)}%
                </span>
              </div>
              <div className="bg-gray-100 rounded-full h-3 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-purple-600 to-indigo-600 h-full transition-all duration-500 ease-out"
                  style={{ width: `${renderData?.progress ?? 0}%` }}
                />
              </div>
              <p className="text-xs text-gray-400 mt-2">
                {renderData?.progress !== undefined && renderData.progress < 50
                  ? '正在下载视频片段...'
                  : renderData?.progress !== undefined && renderData.progress < 70
                  ? '正在合并视频...'
                  : renderData?.progress !== undefined && renderData.progress < 85
                  ? '正在添加音频...'
                  : renderData?.progress !== undefined && renderData.progress < 100
                  ? '正在烧录字幕...'
                  : '即将完成...'}
              </p>
            </>
          )}

          {isComplete && (
            <>
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <CheckCircle className="w-10 h-10 text-green-600" />
              </div>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">生成完成</h1>
              <p className="text-gray-500 mb-6">
                您的混剪视频已生成成功！
              </p>
              <div className="space-y-3">
                <button className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white py-3 rounded-xl font-semibold hover:from-purple-700 hover:to-indigo-700">
                  <Download className="w-5 h-5" />
                  下载视频
                </button>
                <Link
                  to="/"
                  className="w-full flex items-center justify-center gap-2 border border-gray-300 py-3 rounded-xl font-semibold hover:bg-gray-50"
                >
                  <Home className="w-5 h-5" />
                  返回首页
                </Link>
              </div>
            </>
          )}

          {isFailed && (
            <>
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <span className="text-3xl">!</span>
              </div>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">生成失败</h1>
              <p className="text-gray-500 mb-6">
                视频生成过程中出现错误，请重试。
              </p>
              <Link
                to={`/status/${mixId}`}
                className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white py-3 rounded-xl font-semibold hover:from-purple-700 hover:to-indigo-700"
              >
                <ArrowLeft className="w-5 h-5" />
                返回重试
              </Link>
            </>
          )}

          {!jobId && !isLoading && (
            <div>
              <p className="text-gray-500 mb-6">正在获取任务状态...</p>
              <Link
                to="/"
                className="text-purple-600 hover:text-purple-700"
              >
                返回首页
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
