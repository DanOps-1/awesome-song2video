import { Link } from 'react-router-dom'
import { Typography, Button, Row, Col } from 'antd'
import { CustomerServiceOutlined, ThunderboltOutlined, PlayCircleOutlined, RocketOutlined, GithubOutlined } from '@ant-design/icons'
import { motion } from 'framer-motion'

const { Title, Paragraph, Text } = Typography

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.2
    }
  }
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: { type: "spring", stiffness: 100 }
  }
}

const FeatureCard = ({ icon, title, desc }: { icon: React.ReactNode, title: string, desc: string }) => (
  <motion.div 
    variants={itemVariants}
    whileHover={{ y: -10, transition: { duration: 0.2 } }}
    className="h-full"
  >
    <div className="glass p-8 rounded-2xl h-full flex flex-col items-center text-center hover:bg-white/10 transition-colors duration-300">
      <div className="w-16 h-16 bg-gradient-to-br from-violet-500/20 to-fuchsia-500/20 rounded-2xl flex items-center justify-center mb-6 text-violet-300 shadow-inner ring-1 ring-white/10">
        {icon}
      </div>
      <Title level={4} style={{ color: 'white', marginTop: 0, marginBottom: 12 }}>{title}</Title>
      <Text style={{ color: 'rgba(255,255,255,0.6)', fontSize: 15, lineHeight: 1.6 }}>{desc}</Text>
    </div>
  </motion.div>
)

export default function Home() {
  return (
    <motion.div 
      initial="hidden"
      animate="visible"
      variants={containerVariants}
      className="min-h-[90vh] flex flex-col items-center justify-center px-6 py-20 relative overflow-hidden"
    >
      {/* Background Decor */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-violet-600/20 rounded-full blur-[100px] pointer-events-none mix-blend-screen animate-pulse" />
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-fuchsia-600/20 rounded-full blur-[100px] pointer-events-none mix-blend-screen animate-pulse" style={{ animationDelay: '2s' }} />

      <motion.div variants={itemVariants} className="text-center z-10 mb-20 max-w-3xl">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-violet-200 text-sm font-medium mb-8 backdrop-blur-md">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-violet-500"></span>
          </span>
          AI 驱动的音乐可视化引擎 v2.0
        </div>
        
        <Title style={{ 
          color: 'white', 
          fontSize: 'clamp(3rem, 6vw, 5rem)', 
          fontWeight: 800, 
          letterSpacing: '-0.02em',
          lineHeight: 1.1,
          marginBottom: 24,
          textShadow: '0 20px 40px rgba(0,0,0,0.3)'
        }}>
          让你的音乐 <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-fuchsia-400">
            看见画面
          </span>
        </Title>
        
        <Paragraph style={{ fontSize: '1.25rem', color: 'rgba(255,255,255,0.7)', maxWidth: 600, margin: '0 auto 40px' }}>
          上传音频，AI 自动识别歌词情感，智能匹配百万级高清视频素材，一键生成电影级音乐 MV。
        </Paragraph>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link to="/create">
            <Button 
              type="primary" 
              size="large" 
              shape="round" 
              icon={<RocketOutlined />} 
              style={{ 
                height: 56, 
                padding: '0 40px', 
                fontSize: 18, 
                background: 'linear-gradient(135deg, #8b5cf6 0%, #d946ef 100%)',
                border: 'none',
                boxShadow: '0 10px 25px -5px rgba(139, 92, 246, 0.5)'
              }}
              className="hover:scale-105 active:scale-95 transition-transform"
            >
              立即创作
            </Button>
          </Link>
          <Button 
            size="large" 
            shape="round" 
            icon={<GithubOutlined />} 
            className="text-white border-white/20 hover:bg-white/10 hover:border-white/40 h-14 px-8 text-lg"
            ghost
            href="https://github.com/DanOps-1/awsome-song2video"
            target="_blank"
          >
            GitHub
          </Button>
        </div>
      </motion.div>

      <Row gutter={[24, 24]} className="w-full max-w-6xl z-10">
        <Col xs={24} md={8}>
          <FeatureCard 
            icon={<CustomerServiceOutlined style={{ fontSize: 32 }} />}
            title="音频语义理解"
            desc="深度分析歌词意境、情感走向与音乐节奏，精准提取核心视觉关键词。"
          />
        </Col>

        <Col xs={24} md={8}>
          <FeatureCard 
            icon={<ThunderboltOutlined style={{ fontSize: 32 }} />}
            title="智能素材匹配"
            desc="连接全球顶尖视频库，AI 自动筛选最契合画面的高清片段，支持多语言搜索。"
          />
        </Col>

        <Col xs={24} md={8}>
          <FeatureCard 
            icon={<PlayCircleOutlined style={{ fontSize: 32 }} />}
            title="电影级混剪"
            desc="自动对齐节拍，智能转场，一键生成 1080P/4K 高清视频，支持多种屏幕比例。"
          />
        </Col>
      </Row>
    </motion.div>
  )
}
