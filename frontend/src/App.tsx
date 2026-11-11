import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Chat from './pages/Chat'
import Volunteer from './pages/Volunteer'
import Family from './pages/Family'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/volunteer" element={<Volunteer />} />
        <Route path="/family" element={<Family />} />
      </Routes>
    </BrowserRouter>
  )
}
