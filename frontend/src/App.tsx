import { lazy } from "react"
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom"
import { AuthProvider, GuestOnly, useAuth } from "./auth"
import { Shell } from "./components/Shell"
import { ToastProvider } from "./components/ui"
import { PrivacyPage, SignInPage, SignUpPage, TermsPage } from "./pages/AuthPages"
import { Landing } from "./pages/Landing"
import { NotFound } from "./pages/NotFound"
import { WorkspaceProvider } from "./workspace"

const Overview = lazy(() => import("./pages/Overview").then((module) => ({ default: module.Overview })))
const ResumePage = lazy(() => import("./pages/ResumePage").then((module) => ({ default: module.ResumePage })))
const JobPage = lazy(() => import("./pages/JobPage").then((module) => ({ default: module.JobPage })))
const GapsPage = lazy(() => import("./pages/GapsPage").then((module) => ({ default: module.GapsPage })))
const GithubPage = lazy(() => import("./pages/GithubPage").then((module) => ({ default: module.GithubPage })))
const RoadmapPage = lazy(() => import("./pages/RoadmapPage").then((module) => ({ default: module.RoadmapPage })))
const ReportsPage = lazy(() => import("./pages/ReportsPage").then((module) => ({ default: module.ReportsPage })))
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((module) => ({ default: module.SettingsPage })))

function RequireAuth() {
  const auth = useAuth()
  const location = useLocation()
  if (auth.status === "loading") {
    return <p role="status" className="px-4 py-10 text-sm text-[var(--muted)]">Checking your session…</p>
  }
  if (!auth.user) {
    const next = encodeURIComponent(`${location.pathname}${location.search}`)
    return <Navigate to={`/sign-in?next=${next}`} replace />
  }
  return <Shell />
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/sign-in" element={<GuestOnly><SignInPage /></GuestOnly>} />
      <Route path="/sign-up" element={<GuestOnly><SignUpPage /></GuestOnly>} />
      <Route path="/terms" element={<TermsPage />} />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="/app" element={<Navigate to="/dashboard" replace />} />
      <Route path="/app/resume" element={<Navigate to="/resume-analyzer" replace />} />
      <Route path="/app/job" element={<Navigate to="/job-matcher" replace />} />
      <Route path="/app/gaps" element={<Navigate to="/skill-gap" replace />} />
      <Route path="/app/github" element={<Navigate to="/github-intelligence" replace />} />
      <Route path="/app/roadmap" element={<Navigate to="/career-roadmap" replace />} />
      <Route path="/app/reports" element={<Navigate to="/reports" replace />} />
      <Route path="/app/settings" element={<Navigate to="/settings" replace />} />
      <Route element={<RequireAuth />}>
        <Route path="/dashboard" element={<Overview />} />
        <Route path="/resume-analyzer" element={<ResumePage />} />
        <Route path="/job-matcher" element={<JobPage />} />
        <Route path="/skill-gap" element={<GapsPage />} />
        <Route path="/github-intelligence" element={<GithubPage />} />
        <Route path="/career-roadmap" element={<RoadmapPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <WorkspaceProvider>
        <ToastProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </ToastProvider>
      </WorkspaceProvider>
    </AuthProvider>
  )
}
