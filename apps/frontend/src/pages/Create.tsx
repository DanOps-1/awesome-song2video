import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { 
  Form, 
  Input, 
  Select, 
  Button, 
  Upload, 
  Typography, 
  message, 
  Tooltip
} from 'antd'
import {
  InboxOutlined,
  ArrowLeftOutlined,
  CloudUploadOutlined,
  MobileOutlined,
  DesktopOutlined,
  AppstoreOutlined,
  BorderOutlined,
  CustomerServiceOutlined,
  LoadingOutlined
} from '@ant-design/icons'
import { motion, AnimatePresence } from 'framer-motion'
import { createMix, fetchLyrics, uploadAudio } from '@/api/mix'
import type { UploadFile, RcFile } from 'antd/es/upload/interface'

const { Title, Text } = Typography
const { Dragger } = Upload
const { Option } = Select

const containerVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } },
  exit: { opacity: 0, y: -20, transition: { duration: 0.3 } }
}

const RadioCard = ({ active, onClick, icon, title, desc, badge }: any) => (
  <div 
    onClick={onClick}
    className={`
      relative overflow-hidden cursor-pointer rounded-xl border p-4 transition-all duration-300
      ${active 
        ? 'border-violet-500 bg-violet-500/10 shadow-[0_0_20px_rgba(139,92,246,0.3)]' 
        : 'border-white/10 bg-white/5 hover:bg-white/10 hover:border-white/20'
      }
    `}
  >
    {active && (
      <motion.div 
        layoutId="activeBorder"
        className="absolute inset-0 border-2 border-violet-500 rounded-xl pointer-events-none"
      />
    )}
    {badge && (
      <div className="absolute top-0 right-0 px-2 py-0.5 text-[10px] font-bold text-white bg-gradient-to-r from-green-400 to-emerald-500 rounded-bl-lg">
        {badge}
      </div>
    )}
    <div className="flex flex-col items-center text-center gap-2">
      <div className={`text-2xl ${active ? 'text-violet-400' : 'text-gray-400'}`}>{icon}</div>
      <div>
        <div className={`font-semibold text-sm ${active ? 'text-white' : 'text-gray-300'}`}>{title}</div>
        <div className="text-[10px] text-gray-500 mt-1">{desc}</div>
      </div>
    </div>
  </div>
)

export default function Create() {
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [fileList, setFileList] = useState<UploadFile[]>([])
  const [aspectRatio, setAspectRatio] = useState('9:16')
  const [messageApi, contextHolder] = message.useMessage()

  const createMutation = useMutation({
    mutationFn: async (values: any) => {
      const file = fileList[0]?.originFileObj
      if (!file) throw new Error('请上传音频文件')

      messageApi.loading({ content: '正在上传音频...', key: 'process' })
      const uploadResult = await uploadAudio(file)

      messageApi.loading({ content: '正在创建任务...', key: 'process' })
      const createPayload = {
        song_title: values.song_title,
        artist: values.artist,
        source_type: 'upload',
        audio_asset_id: uploadResult.id,
        language: values.language,
        aspect_ratio: aspectRatio, // use state
      }
      
      const mix = await createMix(createPayload)

      messageApi.loading({ content: '正在获取歌词...', key: 'process' })
      fetchLyrics(mix.id)
        .then(() => console.log('Lyrics fetched'))
        .catch((err) => console.error('Lyrics fetch failed:', err))
      return mix
    },
    onSuccess: (mix) => {
      messageApi.success({ content: '创建成功！即将跳转...', key: 'process' })
      setTimeout(() => navigate(`/status/${mix.id}`), 1000)
    },
    onError: (error: Error) => {
      messageApi.error({ content: `创建失败: ${error.message}`, key: 'process' })
    }
  })

  const onFinish = (values: any) => {
    if (fileList.length === 0) return messageApi.error('请上传音频文件')
    createMutation.mutate(values)
  }

  const handleFileChange = (info: any) => {
    let newFileList = [...info.fileList].slice(-1)
    setFileList(newFileList)
    if (info.file.status !== 'removed' && newFileList.length > 0) {
       const file = newFileList[0]
       if (file.name && !form.getFieldValue('song_title')) {
         form.setFieldsValue({ song_title: file.name.replace(/\.[^/.]+$/, '') })
       }
    }
  }

  return (
    <motion.div 
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
      className="w-full max-w-3xl mx-auto px-4 py-8"
    >
      {contextHolder}
      <Link to="/" className="inline-flex items-center gap-2 text-white/50 hover:text-white mb-8 transition-colors group">
        <ArrowLeftOutlined className="group-hover:-translate-x-1 transition-transform" /> 返回首页
      </Link>

      <div className="glass rounded-3xl p-8 md:p-12 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-violet-500/10 rounded-full blur-[80px] -translate-y-1/2 translate-x-1/2 pointer-events-none" />

        <div className="mb-10 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 to-fuchsia-600 mb-4 shadow-lg shadow-violet-500/30">
            <CustomerServiceOutlined className="text-3xl text-white" />
          </div>
          <Title level={2} style={{ color: 'white', marginBottom: 8 }}>开始创作</Title>
          <Text className="text-white/50">上传音频，配置参数，开启 AI 视觉之旅</Text>
        </div>

        <Form
          form={form}
          layout="vertical"
          onFinish={onFinish}
          initialValues={{ language: 'auto' }}
          size="large"
          className="space-y-6"
        >
          <Form.Item label={<span className="text-white/80">音频文件</span>} required tooltip="支持 MP3, WAV, FLAC, M4A, AAC">
            <Dragger
              fileList={fileList}
              onChange={handleFileChange}
              beforeUpload={(file) => {
                const isAudio = file.type.startsWith('audio/') || ['.mp3','.wav','.flac','.m4a','.aac'].some(ext => file.name.toLowerCase().endsWith(ext))
                if (!isAudio) messageApi.error('只能上传音频文件!')
                return false
              }}
              maxCount={1}
              style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.1)', borderRadius: 12 }}
              className="hover:!border-violet-500/50 transition-colors"
            >
              <div className="py-4 group">
                <p className="ant-upload-drag-icon">
                  <InboxOutlined className="text-violet-400 group-hover:scale-110 transition-transform duration-300" style={{ fontSize: 32 }} />
                </p>
                <p className="text-white/80 text-lg font-medium mt-4">点击或拖拽文件到此处</p>
                <p className="text-white/40 text-sm mt-2">支持 20MB 以内的音频文件</p>
              </div>
            </Dragger>
          </Form.Item>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Form.Item name="song_title" label={<span className="text-white/80">歌曲名称</span>} rules={[{ required: true, message: '请输入歌曲名称' }]}>
              <Input placeholder="输入歌曲名称" className="glass-input" />
            </Form.Item>
            <Form.Item name="artist" label={<span className="text-white/80">歌手</span>}>
              <Input placeholder="输入歌手名" className="glass-input" />
            </Form.Item>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Form.Item name="language" label={<span className="text-white/80">语言</span>}>
              <Select styles={{ popup: { background: '#1f1f3a' } }}>
                <Option value="auto">自动检测</Option>
                <Option value="zh">中文</Option>
                <Option value="en">英文</Option>
              </Select>
            </Form.Item>
            
            <Form.Item label={<span className="text-white/80">视频比例</span>}>
              <div className="grid grid-cols-4 gap-3">
                {[
                  { value: '9:16', label: '9:16', desc: '抖音/快手', icon: <MobileOutlined />, badge: '热门' },
                  { value: '16:9', label: '16:9', desc: 'B站/YT', icon: <DesktopOutlined /> },
                  { value: '1:1', label: '1:1', desc: 'INS/微信', icon: <AppstoreOutlined /> },
                  { value: '4:3', label: '4:3', desc: '复古', icon: <BorderOutlined /> },
                ].map(item => (
                  <RadioCard 
                    key={item.value}
                    active={aspectRatio === item.value}
                    onClick={() => setAspectRatio(item.value)}
                    {...item}
                  />
                ))}
              </div>
            </Form.Item>
          </div>

          <Form.Item className="mb-0 pt-4">
            <Button 
              type="primary" 
              htmlType="submit" 
              size="large" 
              block 
              loading={createMutation.isPending}
              icon={createMutation.isPending ? <LoadingOutlined /> : <CloudUploadOutlined />}
              style={{ 
                height: 56, 
                fontSize: 18, 
                background: 'linear-gradient(135deg, #8b5cf6 0%, #d946ef 100%)',
                border: 'none',
                boxShadow: '0 8px 20px -4px rgba(139, 92, 246, 0.5)'
              }}
              className="hover:scale-[1.02] active:scale-[0.98] transition-transform"
            >
              {createMutation.isPending ? '正在处理中...' : '开始生成视频'}
            </Button>
          </Form.Item>
        </Form>
      </div>
    </motion.div>
  )
}
