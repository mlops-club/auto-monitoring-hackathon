import { Route, Routes } from 'react-router-dom'
import { ClusterDashboard } from './components/ClusterDashboard'
import './App.css'

function App() {
  return (
    <Routes>
      <Route path="/" element={<ClusterDashboard />} />
      <Route path="/clusters/:clusterName" element={<ClusterDashboard />} />
    </Routes>
  )
}

export default App
