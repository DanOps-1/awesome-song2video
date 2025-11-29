import { useQuery, useMutation } from '@tanstack/react-query'
import { Cpu, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import { getRetrieverStatus, switchRetriever } from '@/api/config'

const backendInfo: Record<string, { name: string; description: string }> = {
  twelvelabs: {
    name: 'TwelveLabs',
    description: '云端视频理解 API，支持语义搜索、多模态检索',
  },
  clip: {
    name: 'CLIP (本地)',
    description: '本地 OpenCLIP ViT-L-14 模型，视觉-文本联合编码',
  },
  vlm: {
    name: 'VLM',
    description: '视觉语言模型，结合视频描述和文本嵌入',
  },
}

export default function RetrieverConfig() {
  const { data, isLoading } = useQuery({
    queryKey: ['retriever-status'],
    queryFn: getRetrieverStatus,
  })

  const switchMutation = useMutation({
    mutationFn: switchRetriever,
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl space-y-6">
      {/* Current Backend */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center gap-2">
          <Cpu className="h-5 w-5" />
          当前检索后端
        </h3>
        <div className="flex items-center gap-4">
          <div className="flex-1">
            <p className="text-xl font-semibold text-primary-600">
              {backendInfo[data?.current_backend || 'twelvelabs']?.name}
            </p>
            <p className="text-sm text-gray-500 mt-1">
              {backendInfo[data?.current_backend || 'twelvelabs']?.description}
            </p>
          </div>
          <span className="inline-flex items-center gap-1 rounded-full px-3 py-1 text-sm font-medium bg-green-100 text-green-800">
            <CheckCircle className="h-4 w-4" />
            运行中
          </span>
        </div>
      </div>

      {/* Available Backends */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">可用后端</h3>
        <div className="space-y-4">
          {data?.available_backends.map((backend) => {
            const info = backendInfo[backend]
            const status = data.backend_status[backend]
            const isCurrent = backend === data.current_backend

            return (
              <div
                key={backend}
                className={`border rounded-lg p-4 ${
                  isCurrent ? 'border-primary-300 bg-primary-50' : 'border-gray-200'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h4 className="font-medium text-gray-900">{info?.name}</h4>
                      {isCurrent && (
                        <span className="text-xs bg-primary-100 text-primary-700 px-2 py-0.5 rounded">
                          当前
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 mt-1">{info?.description}</p>
                    <div className="mt-2 flex items-center gap-1 text-xs">
                      {status?.available ? (
                        <>
                          <CheckCircle className="h-3 w-3 text-green-600" />
                          <span className="text-green-600">{status.reason}</span>
                        </>
                      ) : (
                        <>
                          <AlertCircle className="h-3 w-3 text-yellow-600" />
                          <span className="text-yellow-600">{status?.reason}</span>
                        </>
                      )}
                    </div>
                  </div>
                  {!isCurrent && (
                    <button
                      onClick={() => switchMutation.mutate(backend as 'twelvelabs' | 'clip' | 'vlm')}
                      disabled={!status?.available || switchMutation.isPending}
                      className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      切换
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Switch Result */}
      {switchMutation.isSuccess && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-yellow-600 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-medium text-yellow-800">需要重启服务</h4>
              <p className="text-sm text-yellow-700 mt-1">
                {switchMutation.data?.message}
              </p>
              <p className="text-sm text-yellow-600 mt-2">
                请更新环境变量 <code className="bg-yellow-100 px-1 rounded">RETRIEVER_BACKEND</code> 并重启服务以完成切换。
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Backend Details */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">后端详情</h3>
        <div className="space-y-4">
          <div>
            <h4 className="text-sm font-medium text-gray-700">TwelveLabs</h4>
            <ul className="mt-2 text-sm text-gray-500 list-disc list-inside space-y-1">
              <li>云端服务，需要 API Key</li>
              <li>支持视觉、音频、转录多模态搜索</li>
              <li>需要先上传视频到 TwelveLabs 索引</li>
              <li>适合大规模视频库</li>
            </ul>
          </div>
          <div>
            <h4 className="text-sm font-medium text-gray-700">CLIP</h4>
            <ul className="mt-2 text-sm text-gray-500 list-disc list-inside space-y-1">
              <li>本地运行，无需网络</li>
              <li>使用 OpenCLIP ViT-L-14 模型</li>
              <li>需要 GPU 加速</li>
              <li>适合中小规模视频库</li>
            </ul>
          </div>
          <div>
            <h4 className="text-sm font-medium text-gray-700">VLM</h4>
            <ul className="mt-2 text-sm text-gray-500 list-disc list-inside space-y-1">
              <li>结合视觉语言模型生成视频描述</li>
              <li>使用文本嵌入进行检索</li>
              <li>需要 VLM API（如 GPT-4V）</li>
              <li>描述质量高，但成本较高</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
