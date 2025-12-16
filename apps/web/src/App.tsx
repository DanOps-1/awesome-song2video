import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import TaskList from './pages/tasks/TaskList'
import TaskDetail from './pages/tasks/TaskDetail'
import VideoLibrary from './pages/assets/VideoLibrary'
import AudioLibrary from './pages/assets/AudioLibrary'
import GeneralConfig from './pages/settings/GeneralConfig'
import RetrieverConfig from './pages/settings/RetrieverConfig'
import LogViewer from './pages/system/LogViewer'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="tasks" element={<TaskList />} />
        <Route path="tasks/:taskId" element={<TaskDetail />} />
        <Route path="assets/videos" element={<VideoLibrary />} />
        <Route path="assets/audios" element={<AudioLibrary />} />
        <Route path="settings" element={<GeneralConfig />} />
        <Route path="settings/retriever" element={<RetrieverConfig />} />
        <Route path="logs" element={<LogViewer />} />
      </Route>
    </Routes>
  )
}

export default App
