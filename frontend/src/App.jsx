import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import AppealPage from './pages/AppealPage'
import CasesPage from './pages/CasesPage'
import AnalyticsPage from './pages/AnalyticsPage'

export default function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<Navigate to="/appeal" replace />} />
        <Route path="/appeal" element={<AppealPage />} />
        <Route path="/cases" element={<CasesPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
      </Routes>
    </AppLayout>
  )
}
