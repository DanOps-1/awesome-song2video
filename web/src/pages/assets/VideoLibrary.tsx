import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Search,
  Upload,
  Trash2,
  Film,
  HardDrive,
  RefreshCw,
  ChevronLeft,
  ChevronRight
} from 'lucide-react'
import { listVideos, uploadVideo, deleteVideo, reindexVideo } from '@/api/assets'

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

export default function VideoLibrary() {
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['videos', page, keyword],
    queryFn: () => listVideos({ page, page_size: 20, keyword: keyword || undefined }),
  })

  const uploadMutation = useMutation({
    mutationFn: uploadVideo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['videos'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteVideo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['videos'] })
    },
  })

  const reindexMutation = useMutation({
    mutationFn: reindexVideo,
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
              placeholder="搜索视频..."
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
            accept="video/*"
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadMutation.isPending}
            className="inline-flex items-center gap-2 bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            <Upload className="h-4 w-4" />
            {uploadMutation.isPending ? '上传中...' : '上传视频'}
          </button>
        </div>
      </div>

      {/* Stats */}
      {data && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 flex items-center gap-6">
          <div className="flex items-center gap-2">
            <Film className="h-5 w-5 text-gray-400" />
            <span className="text-sm text-gray-600">共 {data.total} 个视频</span>
          </div>
        </div>
      )}

      {/* Grid */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {data?.videos.map((video) => (
            <div
              key={video.id}
              className="bg-white rounded-xl border border-gray-200 overflow-hidden hover:shadow-md transition-shadow"
            >
              <div className="aspect-video bg-gray-100 flex items-center justify-center">
                <Film className="h-12 w-12 text-gray-300" />
              </div>
              <div className="p-4">
                <h4 className="font-medium text-gray-900 truncate" title={video.filename}>
                  {video.filename}
                </h4>
                <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <HardDrive className="h-3 w-3" />
                    {formatBytes(video.size_bytes)}
                  </span>
                  <span className={`px-2 py-0.5 rounded ${
                    video.index_status === 'indexed' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                  }`}>
                    {video.index_status}
                  </span>
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <button
                    onClick={() => reindexMutation.mutate(video.id)}
                    disabled={reindexMutation.isPending}
                    className="flex-1 inline-flex items-center justify-center gap-1 px-3 py-1.5 text-xs border border-gray-300 rounded-lg hover:bg-gray-50"
                  >
                    <RefreshCw className="h-3 w-3" />
                    重新索引
                  </button>
                  <button
                    onClick={() => {
                      if (confirm('确定删除此视频?')) {
                        deleteMutation.mutate(video.id)
                      }
                    }}
                    disabled={deleteMutation.isPending}
                    className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg hover:bg-red-50"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {data?.videos.length === 0 && (
        <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
          <Film className="h-12 w-12 mx-auto text-gray-300" />
          <p className="mt-2 text-gray-500">暂无视频</p>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="mt-4 text-primary-600 hover:text-primary-700"
          >
            上传第一个视频
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
            disabled={data.videos.length < data.page_size}
            className="p-2 border border-gray-300 rounded-lg disabled:opacity-50 hover:bg-gray-50"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  )
}
