import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { csrfHeaders } from "./api"
import { useAuth } from "./auth"
import type { CareerReport, GitHubAnalysis, JobAnalysis, ResumeAnalysis } from "./types"

const STORAGE_KEY = "careernavigator.workspace.v1"

export type ThemeName = "light" | "dark"

export type Snapshot = {
  id: string
  at: string
  label: string
  skillCount: number
  readiness: number | null
  resume: ResumeAnalysis | null
  job: JobAnalysis | null
  jobDraft: string
  analyzedJobText: string
  jobTitle: string
  company: string
  github: GitHubAnalysis | null
  career: CareerReport | null
  targetCareer: string
  progress: Record<string, boolean>
}

export type WorkspaceData = {
  resume: ResumeAnalysis | null
  job: JobAnalysis | null
  jobDraft: string
  analyzedJobText: string
  jobTitle: string
  company: string
  github: GitHubAnalysis | null
  career: CareerReport | null
  careerStale: boolean
  targetCareer: string
  useOcr: boolean
  weeklyHours: string
  theme: ThemeName
  progress: Record<string, boolean>
  history: Snapshot[]
}

type WorkspaceApi = WorkspaceData & {
  persistWarning: string | null
  setResume: (resume: ResumeAnalysis) => void
  setJob: (job: JobAnalysis, source: string) => void
  setJobDraft: (jobDraft: string) => void
  setJobMeta: (jobTitle: string, company: string) => void
  setGithub: (github: GitHubAnalysis) => void
  setCareer: (career: CareerReport) => void
  setTargetCareer: (value: string) => void
  setUseOcr: (value: boolean) => void
  setWeeklyHours: (value: string) => void
  setTheme: (theme: ThemeName) => void
  toggleProgress: (key: string) => void
  restore: (id: string) => void
  removeSnapshot: (id: string) => void
  clearCurrent: () => void
  clearResume: () => void
  clearAll: () => void
}

const WorkspaceContext = createContext<WorkspaceApi | null>(null)

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function preferredTheme(): ThemeName {
  return "light"
}

function fresh(): WorkspaceData {
  return {
    resume: null,
    job: null,
    jobDraft: "",
    analyzedJobText: "",
    jobTitle: "",
    company: "",
    github: null,
    career: null,
    careerStale: false,
    targetCareer: "",
    useOcr: false,
    weeklyHours: "",
    theme: preferredTheme(),
    progress: {},
    history: [],
  }
}

function asAnalysis<T extends { status: string }>(value: unknown): T | null {
  if (!isRecord(value) || typeof value.status !== "string") return null
  return value as T
}

function asProgress(value: unknown): Record<string, boolean> {
  if (!isRecord(value)) return {}
  const progress: Record<string, boolean> = {}
  for (const [key, item] of Object.entries(value)) {
    if (typeof item === "boolean") progress[key] = item
  }
  return progress
}

function asSnapshot(value: unknown): Snapshot | null {
  if (!isRecord(value) || typeof value.id !== "string" || typeof value.label !== "string") return null
  return {
    id: value.id,
    at: typeof value.at === "string" ? value.at : "",
    label: value.label,
    skillCount: typeof value.skillCount === "number" ? value.skillCount : 0,
    readiness: typeof value.readiness === "number" ? value.readiness : null,
    resume: asAnalysis<ResumeAnalysis>(value.resume),
    job: asAnalysis<JobAnalysis>(value.job),
    jobDraft: typeof value.jobDraft === "string" ? value.jobDraft : "",
    analyzedJobText: typeof value.analyzedJobText === "string" ? value.analyzedJobText : "",
    jobTitle: typeof value.jobTitle === "string" ? value.jobTitle : "",
    company: typeof value.company === "string" ? value.company : "",
    github: asAnalysis<GitHubAnalysis>(value.github),
    career: isRecord(value.career) ? (value.career as CareerReport) : null,
    targetCareer: typeof value.targetCareer === "string" ? value.targetCareer : "",
    progress: asProgress(value.progress),
  }
}

function storedTheme(): ThemeName {
  try {
    const direct = localStorage.getItem("careernavigator.theme")
    if (direct === "dark" || direct === "light") return direct
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return "light"
    const parsed = JSON.parse(raw) as { theme?: string }
    if (parsed.theme === "dark" || parsed.theme === "light") return parsed.theme
  } catch {
    return "light"
  }
  return "light"
}

function readWorkspace(parsed: unknown, theme: ThemeName): WorkspaceData {
  const base = { ...fresh(), theme }
  if (!isRecord(parsed)) return base
  const history = Array.isArray(parsed.history)
    ? parsed.history.map(asSnapshot).filter((item): item is Snapshot => item !== null).slice(0, 5)
    : []
  return {
    ...base,
    resume: asAnalysis<ResumeAnalysis>(parsed.resume),
    job: asAnalysis<JobAnalysis>(parsed.job),
    jobDraft: typeof parsed.jobDraft === "string" ? parsed.jobDraft : "",
    analyzedJobText: typeof parsed.analyzedJobText === "string" ? parsed.analyzedJobText : "",
    jobTitle: typeof parsed.jobTitle === "string" ? parsed.jobTitle : "",
    company: typeof parsed.company === "string" ? parsed.company : "",
    github: asAnalysis<GitHubAnalysis>(parsed.github),
    career: isRecord(parsed.career) ? (parsed.career as CareerReport) : null,
    careerStale: parsed.careerStale === true,
    targetCareer: typeof parsed.targetCareer === "string" ? parsed.targetCareer : "",
    useOcr: parsed.useOcr === true,
    weeklyHours: typeof parsed.weeklyHours === "string" ? parsed.weeklyHours : "",
    theme: parsed.theme === "dark" || parsed.theme === "light" ? parsed.theme : theme,
    progress: asProgress(parsed.progress),
    history,
  }
}

function uid() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID()
  return `id-${Date.now()}`
}

function withSnapshot(data: WorkspaceData, label: string): WorkspaceData {
  const estimate = data.career?.readiness?.estimate
  const snap: Snapshot = {
    id: uid(),
    at: new Date().toISOString(),
    label,
    skillCount: data.resume?.skills?.length ?? 0,
    readiness: typeof estimate === "number" ? estimate : null,
    resume: data.resume,
    job: data.job,
    jobDraft: data.jobDraft,
    analyzedJobText: data.analyzedJobText,
    jobTitle: data.jobTitle,
    company: data.company,
    github: data.github,
    career: data.career,
    targetCareer: data.targetCareer,
    progress: data.progress,
  }
  return { ...data, history: [snap, ...data.history].slice(0, 5) }
}

function usable(status: string) {
  return status === "success" || status === "partial"
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const auth = useAuth()
  const [data, setData] = useState<WorkspaceData>(() => ({ ...fresh(), theme: storedTheme() }))
  const [persistWarning, setPersistWarning] = useState<string | null>(null)
  const hydratedFor = useRef<string | null>(null)

  useEffect(() => {
    document.documentElement.classList.toggle("dark", data.theme === "dark")
    document.documentElement.style.colorScheme = data.theme
    localStorage.setItem("careernavigator.theme", data.theme)
  }, [data.theme])

  useEffect(() => {
    if (auth.status !== "ready") return
    let cancelled = false
    const key = auth.user?.email ?? ""
    async function hydrate() {
      if (!auth.user) {
        if (cancelled) return
        setData((current) => ({ ...fresh(), theme: current.theme }))
        hydratedFor.current = ""
        return
      }
      localStorage.removeItem(STORAGE_KEY)
      try {
        const response = await fetch("/api/me/workspace", { credentials: "include" })
        const body = response.ok ? await response.json().catch(() => null) : null
        if (cancelled) return
        const workspace = body && typeof body === "object" ? (body as { workspace?: unknown }).workspace : null
        setData(readWorkspace(workspace, storedTheme()))
      } catch {
        if (!cancelled) setData((current) => ({ ...fresh(), theme: current.theme }))
      }
      hydratedFor.current = key
    }
    void hydrate()
    return () => {
      cancelled = true
    }
  }, [auth.status, auth.user])

  useEffect(() => {
    if (!auth.user || hydratedFor.current !== auth.user.email) return
    const handle = window.setTimeout(() => {
      void fetch("/api/me/workspace", {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...csrfHeaders() },
        body: JSON.stringify({ workspace: data }),
      }).then((response) => {
        if (!response.ok) {
          setPersistWarning("Your analysis could not be saved to your account. It is still on this screen.")
        }
      }).catch(() => {
        setPersistWarning("Your analysis could not be saved to your account. It is still on this screen.")
      })
    }, 400)
    return () => window.clearTimeout(handle)
  }, [auth.user, data])

  const api = useMemo<WorkspaceApi>(() => {
    const update = (recipe: (current: WorkspaceData) => WorkspaceData) => {
      setData((current) => recipe(current))
    }
    return {
      ...data,
      persistWarning,
      setResume: (resume) =>
        update((current) => {
          const next: WorkspaceData = { ...current, resume, career: null, careerStale: false, progress: {} }
          return usable(resume.status) ? withSnapshot(next, `Resume · ${resume.file_name || "upload"}`) : next
        }),
      setJob: (job, source) =>
        update((current) => {
          const next: WorkspaceData = {
            ...current,
            job,
            jobDraft: source,
            analyzedJobText: source,
            career: null,
            careerStale: false,
            progress: {},
          }
          return usable(job.status) ? withSnapshot(next, "Job description") : next
        }),
      setJobDraft: (jobDraft) => update((current) => ({ ...current, jobDraft })),
      setJobMeta: (jobTitle, company) => update((current) => ({ ...current, jobTitle, company })),
      setGithub: (github) =>
        update((current) =>
          withSnapshot(
            { ...current, github, careerStale: current.career !== null },
            `GitHub · ${github.username || github.status}`,
          ),
        ),
      setCareer: (career) => update((current) => withSnapshot({ ...current, career, careerStale: false }, "Career report")),
      setTargetCareer: (targetCareer) => update((current) => ({ ...current, targetCareer })),
      setUseOcr: (useOcr) => update((current) => ({ ...current, useOcr })),
      setWeeklyHours: (weeklyHours) => update((current) => ({ ...current, weeklyHours })),
      setTheme: (theme) => update((current) => ({ ...current, theme })),
      toggleProgress: (key) =>
        update((current) => ({
          ...current,
          progress: { ...current.progress, [key]: !current.progress[key] },
        })),
      restore: (id) =>
        update((current) => {
          const snap = current.history.find((item) => item.id === id)
          if (!snap) return current
          return {
            ...current,
            resume: snap.resume,
            job: snap.job,
            jobDraft: snap.jobDraft,
            analyzedJobText: snap.analyzedJobText,
            jobTitle: snap.jobTitle,
            company: snap.company,
            github: snap.github,
            career: snap.career,
            targetCareer: snap.targetCareer,
            progress: snap.progress,
            careerStale: false,
          }
        }),
      removeSnapshot: (id) =>
        update((current) => ({ ...current, history: current.history.filter((item) => item.id !== id) })),
      clearResume: () =>
        update((current) => ({
          ...current,
          resume: null,
          career: null,
          careerStale: false,
          progress: {},
        })),
      clearCurrent: () =>
        update((current) => ({
          ...current,
          resume: null,
          job: null,
          jobDraft: "",
          analyzedJobText: "",
          jobTitle: "",
          company: "",
          github: null,
          career: null,
          careerStale: false,
          progress: {},
        })),
      clearAll: () =>
        update((current) => ({
          ...fresh(),
          theme: current.theme,
          useOcr: current.useOcr,
          weeklyHours: current.weeklyHours,
          targetCareer: current.targetCareer,
        })),
    }
  }, [data, persistWarning])

  return <WorkspaceContext.Provider value={api}>{children}</WorkspaceContext.Provider>
}

export function useWorkspace() {
  const value = useContext(WorkspaceContext)
  if (!value) throw new Error("useWorkspace must be used inside WorkspaceProvider")
  return value
}

export function parseWeeklyHours(value: string): { hours: number | null; error: string | null } {
  const trimmed = value.trim()
  if (!trimmed) return { hours: null, error: null }
  if (!/^[1-9]\d*$/.test(trimmed)) {
    return { hours: null, error: "Weekly hours must be a positive whole number, or left blank." }
  }
  return { hours: Number(trimmed), error: null }
}
