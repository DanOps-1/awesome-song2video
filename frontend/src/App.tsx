import { Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Create from './pages/Create'
import Status from './pages/Status'
import Result from './pages/Result'

function App() {
  return (
    <div className="min-h-screen">
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/create" element={<Create />} />
        <Route path="/status/:mixId" element={<Status />} />
        <Route path="/result/:mixId" element={<Result />} />
      </Routes>
    </div>
  )
}

export default App
