import type { CareerReport, GitHubAnalysis, JobAnalysis, ReportBundle, ResumeAnalysis } from "./types"

const base = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "")

export class ApiError extends Error {
  status: number
  errors: string[]

  constructor(message: string, status: number, errors: string[]) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.errors = errors
  }
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text) as unknown
  } catch {
    return null
  }
}

function fail(response: Response, body: unknown): ApiError {
  const record = body && typeof body === "object" ? (body as { errors?: unknown }) : {}
  const errors = Array.isArray(record.errors)
    ? record.errors.filter((item): item is string => typeof item === "string")
    : [`The request failed (${response.status}).`]
  return new ApiError(errors[0] ?? `The request failed (${response.status}).`, response.status, errors)
}

const UNREACHABLE = "The analysis service could not be reached. Start it and reload this page."

export function csrfHeaders(): Record<string, string> {
  if (typeof document === "undefined") return {}
  const match = document.cookie.match(/(?:^|; )cn_csrf=([^;]*)/)
  const token = match ? decodeURIComponent(match[1]) : ""
  return token ? { "X-CSRF-Token": token } : {}
}

async function request(path: string, init: RequestInit, timeoutMs: number) {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  const headers = new Headers(init.headers)
  const method = (init.method ?? "GET").toUpperCase()
  if (method !== "GET" && method !== "HEAD") {
    for (const [key, value] of Object.entries(csrfHeaders())) headers.set(key, value)
  }
  try {
    return await fetch(`${base}${path}`, { ...init, headers, credentials: "include", signal: controller.signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The request timed out. The analysis service took too long to respond.", 0, [])
    }
    throw new ApiError(UNREACHABLE, 0, [])
  } finally {
    window.clearTimeout(timer)
  }
}

async function postJson(path: string, payload: unknown, timeoutMs = 20000) {
  const response = await request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }, timeoutMs)
  const body = await readJson(response)
  if (!response.ok) throw fail(response, body)
  return body
}

export async function checkHealth(): Promise<{ ok: boolean; message: string }> {
  try {
    const response = await request("/api/health", { method: "GET" }, 8000)
    const body = (await readJson(response)) as { status?: string; service?: string } | null
    if (!response.ok || body?.status !== "ok") {
      return { ok: false, message: "The analysis API responded, but not with a healthy status." }
    }
    return { ok: true, message: "The analysis service is reachable." }
  } catch {
    return {
      ok: false,
      message: "The analysis service is not reachable.",
    }
  }
}

export async function analyzeResume(file: File, useOcr: boolean): Promise<ResumeAnalysis> {
  const form = new FormData()
  form.append("file", file)
  form.append("use_ocr", useOcr ? "true" : "false")
  const response = await request("/api/resume", { method: "POST", body: form }, 90000)
  const body = await readJson(response)
  if (!response.ok) throw fail(response, body)
  return body as ResumeAnalysis
}

export async function analyzeJob(text: string): Promise<JobAnalysis> {
  return (await postJson("/api/job", { text })) as JobAnalysis
}

export async function analyzeGithub(username: string): Promise<GitHubAnalysis> {
  return (await postJson("/api/github", { username }, 30000)) as GitHubAnalysis
}

export async function buildCareerReport(input: {
  resume: ResumeAnalysis
  job: JobAnalysis | null
  github: GitHubAnalysis | null
  weeklyHours: number | null
}): Promise<CareerReport> {
  return (await postJson("/api/career-report", {
    resume: input.resume,
    job: input.job,
    github: input.github,
    weekly_hours: input.weeklyHours,
  })) as CareerReport
}

export async function buildReport(input: {
  resume: ResumeAnalysis
  job: JobAnalysis | null
  github: GitHubAnalysis | null
  weeklyHours: number | null
  jobTitle: string
  company: string
  targetCareer: string
}): Promise<ReportBundle> {
  return (await postJson("/api/report", {
    resume: input.resume,
    job: input.job,
    github: input.github,
    weekly_hours: input.weeklyHours,
    job_title: input.jobTitle,
    company: input.company,
    target_career: input.targetCareer,
  })) as ReportBundle
}

export function pipelineProblem(result: {
  status?: string
  errors?: string[]
  reason?: string | null
  warnings?: string[]
}): string | null {
  if (!result.status || result.status === "success" || result.status === "partial") return null
  return result.errors?.[0] || result.reason || `The pipeline returned status “${result.status}”.`
}
