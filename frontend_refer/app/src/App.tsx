import { Routes, Route } from 'react-router'
import Layout from './components/Layout'
import Home from './pages/Home'
import QuickInput from './pages/QuickInput'
import Processing from './pages/Processing'
import Reports from './pages/Reports'
import ReportDetail from './pages/ReportDetail'
import Pipeline from './pages/Pipeline'
import Customers from './pages/Customers'
import Settings from './pages/Settings'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="input" element={<QuickInput />} />
        <Route path="processing" element={<Processing />} />
        <Route path="reports" element={<Reports />} />
        <Route path="report/:id" element={<ReportDetail />} />
        <Route path="pipeline" element={<Pipeline />} />
        <Route path="customers" element={<Customers />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
