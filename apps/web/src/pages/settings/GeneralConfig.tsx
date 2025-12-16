import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect } from 'react'
import { Save, RefreshCw } from 'lucide-react'
import { getConfig, updateConfig } from '@/api/config'

export default function GeneralConfig() {
  const queryClient = useQueryClient()
  const { data: config, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: getConfig,
  })

  const [formData, setFormData] = useState({
    render_per_video_limit: 2,
    render_max_retry: 2,
    query_rewrite_enabled: true,
    query_rewrite_mandatory: false,
  })

  useEffect(() => {
    if (config) {
      setFormData({
        render_per_video_limit: config.render.per_video_limit,
        render_max_retry: config.render.max_retry,
        query_rewrite_enabled: config.query_rewrite_enabled,
        query_rewrite_mandatory: config.query_rewrite_mandatory,
      })
    }
  }, [config])

  const updateMutation = useMutation({
    mutationFn: updateConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] })
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateMutation.mutate(formData)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl space-y-6">
      {/* Environment Info */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">环境信息</h3>
        <dl className="space-y-3">
          <div className="flex justify-between">
            <dt className="text-sm text-gray-500">运行环境</dt>
            <dd className="text-sm font-medium text-gray-900">{config?.environment}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-sm text-gray-500">检索后端</dt>
            <dd className="text-sm font-medium text-gray-900">{config?.retriever.backend}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-sm text-gray-500">Whisper 模型</dt>
            <dd className="text-sm font-medium text-gray-900">{config?.whisper.model_name}</dd>
          </div>
        </dl>
      </div>

      {/* Editable Settings */}
      <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">可编辑配置</h3>

        <div className="space-y-4">
          {/* Render Settings */}
          <div className="border-b border-gray-200 pb-4">
            <h4 className="text-sm font-medium text-gray-700 mb-3">渲染设置</h4>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-500 mb-1">
                  每视频片段限制
                </label>
                <input
                  type="number"
                  min={1}
                  max={5}
                  value={formData.render_per_video_limit}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    render_per_video_limit: parseInt(e.target.value)
                  }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-500 mb-1">
                  最大重试次数
                </label>
                <input
                  type="number"
                  min={0}
                  max={10}
                  value={formData.render_max_retry}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    render_max_retry: parseInt(e.target.value)
                  }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
          </div>

          {/* Query Rewrite Settings */}
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-3">查询改写设置</h4>
            <div className="space-y-3">
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={formData.query_rewrite_enabled}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    query_rewrite_enabled: e.target.checked
                  }))}
                  className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700">启用查询改写</span>
              </label>
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={formData.query_rewrite_mandatory}
                  onChange={(e) => setFormData(prev => ({
                    ...prev,
                    query_rewrite_mandatory: e.target.checked
                  }))}
                  className="w-4 h-4 text-primary-600 rounded focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700">强制查询改写（首次查询即改写）</span>
              </label>
            </div>
          </div>
        </div>

        <div className="mt-6 flex items-center gap-3">
          <button
            type="submit"
            disabled={updateMutation.isPending}
            className="inline-flex items-center gap-2 bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            <Save className="h-4 w-4" />
            {updateMutation.isPending ? '保存中...' : '保存配置'}
          </button>
          <button
            type="button"
            onClick={() => queryClient.invalidateQueries({ queryKey: ['config'] })}
            className="inline-flex items-center gap-2 border border-gray-300 px-4 py-2 rounded-lg hover:bg-gray-50"
          >
            <RefreshCw className="h-4 w-4" />
            重置
          </button>
        </div>

        {updateMutation.isSuccess && (
          <p className="mt-3 text-sm text-green-600">配置已保存</p>
        )}
        {updateMutation.isError && (
          <p className="mt-3 text-sm text-red-600">保存失败，请重试</p>
        )}
      </form>

      {/* Read-only Info */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">渲染配置（只读）</h3>
        <dl className="space-y-3">
          <div className="flex justify-between">
            <dt className="text-sm text-gray-500">并发限制</dt>
            <dd className="text-sm font-medium text-gray-900">{config?.render.concurrency_limit}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-sm text-gray-500">片段并发</dt>
            <dd className="text-sm font-medium text-gray-900">{config?.render.clip_concurrency}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-sm text-gray-500">重试退避基数</dt>
            <dd className="text-sm font-medium text-gray-900">{config?.render.retry_backoff_base_ms}ms</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-sm text-gray-500">指标刷新间隔</dt>
            <dd className="text-sm font-medium text-gray-900">{config?.render.metrics_flush_interval_s}s</dd>
          </div>
        </dl>
        <p className="mt-4 text-xs text-gray-400">
          这些配置需要修改环境变量并重启服务
        </p>
      </div>
    </div>
  )
}
