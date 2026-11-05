import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import { HOME, useAuth } from './lib/auth'
import type { Role } from './lib/types'
import Login from './pages/Login'

// Route-level code splitting keeps the first load small.
const Roles = lazy(() => import('./pages/Roles'))
const PostJob = lazy(() => import('./pages/PostJob'))
const JobDetail = lazy(() => import('./pages/JobDetail'))
const CommandCenter = lazy(() => import('./pages/CommandCenter'))
const Employees = lazy(() => import('./pages/Employees'))
const Governance = lazy(() => import('./pages/Governance'))
const CareerHub = lazy(() => import('./pages/CareerHub'))
const Insights = lazy(() => import('./pages/Insights'))
const Architecture = lazy(() => import('./pages/Architecture'))

function Guard({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to={HOME[user.role]} replace />
  return <>{children}</>
}

export default function App() {
  const { user } = useAuth()
  return (
    <Suspense fallback={<div className="p-10"><Spinner /></div>}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Guard><Layout /></Guard>}>
          <Route path="/hm" element={<Guard roles={['hiring_manager']}><Roles mine /></Guard>} />
          <Route path="/hm/post" element={<Guard roles={['hiring_manager', 'hr_admin']}><PostJob /></Guard>} />
          <Route path="/jobs/:jobId" element={<Guard roles={['hiring_manager', 'hr_admin', 'leadership']}><JobDetail /></Guard>} />
          <Route path="/hr" element={<Guard roles={['hr_admin']}><CommandCenter /></Guard>} />
          <Route path="/hr/jobs" element={<Guard roles={['hr_admin']}><Roles mine={false} /></Guard>} />
          <Route path="/hr/employees" element={<Guard roles={['hr_admin']}><Employees /></Guard>} />
          <Route path="/hr/governance" element={<Guard roles={['hr_admin', 'leadership']}><Governance /></Guard>} />
          <Route path="/me" element={<Guard roles={['employee']}><CareerHub /></Guard>} />
          <Route path="/insights" element={<Guard roles={['leadership', 'hiring_manager', 'hr_admin']}><Insights /></Guard>} />
          <Route path="/architecture" element={<Architecture />} />
        </Route>
        <Route path="*" element={<Navigate to={user ? HOME[user.role] : '/login'} replace />} />
      </Routes>
    </Suspense>
  )
}
