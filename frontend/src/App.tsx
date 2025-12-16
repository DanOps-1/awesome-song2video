import { Routes, Route, useLocation } from 'react-router-dom'
import { ConfigProvider, App as AntdApp, Layout, theme } from 'antd'
import { AnimatePresence } from 'framer-motion'
import Home from './pages/Home'
import Create from './pages/Create'
import Status from './pages/Status'
import Result from './pages/Result'
import zhCN from 'antd/locale/zh_CN'

const { Content, Footer } = Layout

function App() {
  const location = useLocation()

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#8b5cf6', // Violet-500
          borderRadius: 12,
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif',
          colorBgContainer: 'rgba(30, 41, 59, 0.6)', // Slate-800 with opacity
          colorBgElevated: 'rgba(30, 41, 59, 0.8)',
        },
        components: {
          Card: {
            colorBgContainer: 'rgba(255, 255, 255, 0.03)',
            colorBorderSecondary: 'rgba(255, 255, 255, 0.08)',
          },
          Button: {
            controlHeightLG: 50,
            fontSizeLG: 16,
            fontWeight: 600,
          },
          Input: {
            controlHeightLG: 50,
            colorBgContainer: 'rgba(0, 0, 0, 0.2)',
            activeBorderColor: '#8b5cf6',
          },
          Select: {
            controlHeightLG: 50,
            colorBgContainer: 'rgba(0, 0, 0, 0.2)',
          }
        }
      }}
    >
      <AntdApp>
        <Layout className="min-h-screen bg-transparent">
          <Content>
            <AnimatePresence mode="wait">
              <Routes location={location} key={location.pathname}>
                <Route path="/" element={<Home />} />
                <Route path="/create" element={<Create />} />
                <Route path="/status/:mixId" element={<Status />} />
                <Route path="/result/:mixId" element={<Result />} />
              </Routes>
            </AnimatePresence>
          </Content>
          <Footer style={{ textAlign: 'center', background: 'transparent', color: 'rgba(255,255,255,0.4)' }}>
            Song2Video ©{new Date().getFullYear()} Created by DanOps-1
          </Footer>
        </Layout>
      </AntdApp>
    </ConfigProvider>
  )
}

export default App