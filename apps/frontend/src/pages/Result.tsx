import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getRenderStatus } from '@/api/mix'
import { useState, useEffect } from 'react'
import { Button, Progress, Typography, Spin, Tooltip } from 'antd'
import { DownloadOutlined, HomeOutlined, RedoOutlined, ShareAltOutlined } from '@ant-design/icons'
import { motion } from 'framer-motion'
import confetti from 'canvas-confetti'

const { Title, Paragraph, Text } = Typography

export default function ResultPage() {
  const { mixId } = useParams<{ mixId: string }>()
  const [jobId, setJobId] = useState<string | null>(null)
  const [hasCelebrated, setHasCelebrated] = useState(false)

  useEffect(() => {
    const storedJobId = sessionStorage.getItem(`job_${mixId}`)
    if (storedJobId) setJobId(storedJobId)
  }, [mixId])

  const { data: renderData } = useQuery({
    queryKey: ['render-status', mixId, jobId],
    queryFn: () => getRenderStatus(mixId!, jobId!),
    enabled: !!mixId && !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return (status === 'success' || status === 'failed') ? false : 2000
    },
  })

  const isComplete = renderData?.status === 'success'
  const isFailed = renderData?.status === 'failed'
  const isProcessing = !isComplete && !isFailed

  useEffect(() => {
    if (isComplete && !hasCelebrated) {
      confetti({
        particleCount: 150,
        spread: 70,
        origin: { y: 0.6 },
        colors: ['#8b5cf6', '#d946ef', '#06b6d4']
      })
      setHasCelebrated(true)
    }
  }, [isComplete, hasCelebrated])

  const getProgressText = () => {
    const p = renderData?.progress ?? 0
    if (p < 5) return '正在初始化渲染引擎...'
    if (p < 50) return '正在下载高清视频素材...'
    if (p < 70) return '正在进行智能剪辑与拼接...'
    if (p < 85) return '正在合成音频与背景音乐...'
    if (p < 95) return '正在烧录动态字幕...'
    return '即将完成，请稍候...'
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center p-4">
      <motion.div 
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-2xl"
      >
        <div className="glass rounded-3xl p-8 md:p-12 text-center relative overflow-hidden shadow-2xl shadow-violet-500/10">
          
          {isProcessing && (
            <div className="py-12">
              <div className="relative w-32 h-32 mx-auto mb-8">
                <div className="absolute inset-0 rounded-full border-4 border-white/10" />
                <div className="absolute inset-0 rounded-full border-t-4 border-violet-500 animate-spin" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-2xl font-bold text-white">{Math.round(renderData?.progress ?? 0)}%</span>
                </div>
              </div>
              
              <Title level={2} style={{ color: 'white' }}>视频生成中</Title>
              <Text className="text-white/50 block mb-8 text-lg">{getProgressText()}</Text>
              
              <div className="w-full max-w-md mx-auto h-1.5 bg-white/10 rounded-full overflow-hidden">
                <motion.div 
                  className="h-full bg-gradient-to-r from-violet-500 via-fuchsia-500 to-cyan-500"
                  animate={{ width: `${renderData?.progress ?? 0}%` }}
                />
              </div>
            </div>
          )}

          {isComplete && (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
              <div className="w-20 h-20 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-6 text-green-400 border border-green-500/30">
                <DownloadOutlined style={{ fontSize: 32 }} />
              </div>
              
              <Title level={2} style={{ color: 'white' }}>创作完成！</Title>
              <Paragraph className="text-white/60 text-lg mb-8">
                您的 AI 音乐视频已生成，快来看看效果吧
              </Paragraph>

              {renderData?.output_url && (
                <div className="rounded-2xl overflow-hidden bg-black aspect-video mb-8 shadow-2xl border border-white/10 group relative">
                  <video
                    src={renderData.output_url}
                    controls
                    className="w-full h-full object-contain"
                    playsInline
                  />
                </div>
              )}

              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Button 
                  type="primary" 
                  size="large" 
                  icon={<DownloadOutlined />} 
                  href={renderData?.output_url} 
                  target="_blank" 
                  download
                  className="bg-gradient-to-r from-violet-600 to-fuchsia-600 border-none h-12 px-8"
                >
                  下载高清视频
                </Button>
                <Link to="/">
                  <Button size="large" icon={<HomeOutlined />} className="h-12 px-8" ghost>
                    返回首页
                  </Button>
                </Link>
              </div>
            </motion.div>
          )}

          {isFailed && (
            <div className="py-8">
              <div className="w-20 h-20 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-6 text-red-400 border border-red-500/30">
                <ExclamationCircleOutlined style={{ fontSize: 32 }} />
              </div>
              <Title level={3} style={{ color: 'white' }}>生成失败</Title>
              <Paragraph className="text-white/60 mb-8">抱歉，渲染过程中出现了未知错误</Paragraph>
              
              <div className="flex gap-4 justify-center">
                 <Link to={`/status/${mixId}`}>
                   <Button type="primary" danger size="large" icon={<RedoOutlined />}>重试</Button>
                 </Link>
                 <Link to="/">
                   <Button size="large">返回首页</Button>
                 </Link>
              </div>
            </div>
          )}

          {!jobId && !isProcessing && !isComplete && !isFailed && (
            <Spin tip="正在查询任务..." size="large" className="py-20" />
          )}

        </div>
      </motion.div>
    </div>
  )
}
