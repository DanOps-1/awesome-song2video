import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Search,
  Upload,
  Trash2,
  Music,
  HardDrive,
  Play,
  ChevronLeft,
  ChevronRight
} from 'lucide-react'
import { listAudios, uploadAudio, deleteAudio } from '@/api/assets'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

export default function AudioLibrary() {
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['audios', page, keyword],
    queryFn: () => listAudios({ page, page_size: 20, keyword: keyword || undefined }),
  })

  const uploadMutation = useMutation({
    mutationFn: uploadAudio,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['audios'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteAudio,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['audios'] })
    },
  })

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      uploadMutation.mutate(file)
    }
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <form onSubmit={handleSearch} className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="搜索音频..."
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 w-64"
            />
          </form>
        </div>
        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*"
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadMutation.isPending}
            className="inline-flex items-center gap-2 bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            <Upload className="h-4 w-4" />
            {uploadMutation.isPending ? '上传中...' : '上传音频'}
          </button>
        </div>
      </div>

      {/* Stats */}
      {data && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 flex items-center gap-6">
          <div className="flex items-center gap-2">
            <Music className="h-5 w-5 text-gray-400" />
            <span className="text-sm text-gray-600">共 {data.total} 个音频</span>
          </div>
        </div>
      )}

      {/* List */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  文件名
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  大小
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  创建时间
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  操作
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {data?.audios.map((audio) => (
                <tr key={audio.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-primary-100 rounded-lg">
                        <Music className="h-5 w-5 text-primary-600" />
                      </div>
                      <span className="font-medium text-gray-900">{audio.filename}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    <div className="flex items-center gap-1">
                      <HardDrive className="h-4 w-4" />
                      {formatBytes(audio.size_bytes)}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {new Date(audio.created_at).toLocaleString('zh-CN')}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        className="p-2 text-gray-400 hover:text-primary-600 rounded-lg hover:bg-primary-50"
                        title="播放"
                      >
                        <Play className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => {
                          if (confirm('确定删除此音频?')) {
                            deleteMutation.mutate(audio.id)
                          }
                        }}
                        disabled={deleteMutation.isPending}
                        className="p-2 text-gray-400 hover:text-red-600 rounded-lg hover:bg-red-50"
                        title="删除"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty state */}
      {data?.audios.length === 0 && (
        <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
          <Music className="h-12 w-12 mx-auto text-gray-300" />
          <p className="mt-2 text-gray-500">暂无音频</p>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="mt-4 text-primary-600 hover:text-primary-700"
          >
            上传第一个音频
          </button>
        </div>
      )}

      {/* Pagination */}
      {data && data.total > data.page_size && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="p-2 border border-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-50"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm text-gray-600">
            第 {page} 页
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={data.audios.length < data.page_size}
            className="p-2 border border-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-50"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  )
}
