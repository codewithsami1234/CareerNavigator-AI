import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { analyzeJob, buildCareerReport, pipelineProblem } from "../api"
import { ComparisonDetails, JobDetails, ReadinessDetails } from "../components/views"
import type { CareerReport } from "../types"
import { Alert, Button, Card, Field, inputClass, Skeleton } from "../components/ui"
import { SAMPLE_COMPANY, SAMPLE_JOB, SAMPLE_JOB_TITLE, SCORING_METHOD } from "../demo"
import { parseWeeklyHours, useWorkspace } from "../workspace"

function sameDescription(left: string, right: string) {
  return left.replace(/\r\n/g, "\n").trim() === right.replace(/\r\n/g, "\n").trim()
}

function descriptionDrift(draft: string, analyzed: string, hasJob: boolean) {
  if (!hasJob) return null
  if (!analyzed.trim()) {
    if (draft.trim()) {
      return "Read this description before comparing. The saved result has no copy of the text it came from."
    }
    return null
  }
  if (!sameDescription(draft, analyzed)) {
    return "The box does not match the description that was read. Choose Read job description again before comparing."
  }
  return null
}

export function JobPage() {
  const workspace = useWorkspace()
  const text = workspace.jobDraft
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const wasLoading = useRef(false)
  const drift = descriptionDrift(text, workspace.analyzedJobText, workspace.job !== null)

  useEffect(() => {
    if (wasLoading.current && !loading) {
      document.getElementById("job-results")?.scrollIntoView({ block: "start" })
    }
    wasLoading.current = loading
  }, [loading])

  async function onRead() {
    if (!text.trim()) {
      setError("Paste a job description first. This app does not fetch job listings.")
      return
    }
    setLoading(true)
    setError(null)
    try {
      const job = await analyzeJob(text)
      workspace.setJob(job, text)
      const problem = pipelineProblem(job)
      if (problem) setError(problem)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The job description could not be read.")
    } finally {
      setLoading(false)
    }
  }

  async function onCompare() {
    if (!workspace.resume || (workspace.resume.status !== "success" && workspace.resume.status !== "partial")) {
      setError("Analyze a usable resume before comparing. Failed, empty, and needs_ocr results are not scored.")
      return
    }
    if (!workspace.job || workspace.job.status !== "success") {
      setError("Read a job description that the pipeline accepted before comparing.")
      return
    }
    const mismatch = descriptionDrift(text, workspace.analyzedJobText, true)
    if (mismatch) {
      setError(mismatch)
      return
    }
    const hours = parseWeeklyHours(workspace.weeklyHours)
    if (hours.error) {
      setError(hours.error)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const career = await buildCareerReport({
        resume: workspace.resume,
        job: workspace.job,
        github: workspace.github,
        weeklyHours: hours.hours,
      })
      workspace.setCareer(career)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The comparison could not be built.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      {!workspace.resume ? (
        <Alert tone="warning">
          No resume is saved with this account yet. <Link className="font-medium underline" to="/resume-analyzer">Analyze a resume</Link> before comparing. You can still read a job description on its own.
        </Alert>
      ) : null}
      <Card>
        <h2 className="text-lg font-semibold">Job description you supply</h2>
        <p className="muted mt-1 text-sm leading-6">
          Title and company are report labels. They are not requirements unless they also appear in the description. The box keeps the text last read for this account.
        </p>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <Field label="Job title">
            <input className={inputClass} value={workspace.jobTitle} onChange={(event) => workspace.setJobMeta(event.target.value, workspace.company)} />
          </Field>
          <Field label="Company">
            <input className={inputClass} value={workspace.company} onChange={(event) => workspace.setJobMeta(workspace.jobTitle, event.target.value)} />
          </Field>
        </div>
        <div className="mt-4">
          <Field label="Job description" hint="Headings such as Required qualifications and Preferred qualifications are how the pipeline assigns priority.">
            <textarea className={`${inputClass} min-h-48!`} value={text} onChange={(event) => workspace.setJobDraft(event.target.value)} />
          </Field>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={() => void onRead()} disabled={loading}>{loading ? "Working…" : "Read job description"}</Button>
          <Button onClick={() => void onCompare()} variant="secondary" disabled={loading}>Compare with resume</Button>
          <Button
            variant="ghost"
            onClick={() => {
              workspace.setJobDraft(SAMPLE_JOB)
              workspace.setJobMeta(SAMPLE_JOB_TITLE, SAMPLE_COMPANY)
              if (!workspace.targetCareer) workspace.setTargetCareer("Software engineering")
            }}
          >
            Load synthetic posting
          </Button>
        </div>
      </Card>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {drift && !error ? <Alert tone="warning">{drift}</Alert> : null}
      {workspace.careerStale ? <Alert tone="warning">GitHub was updated after this comparison. Compare again to refresh observations. GitHub does not change the readiness number.</Alert> : null}
      {loading ? <Skeleton /> : null}
      {workspace.job ? (
        <div id="job-results">
          <JobDetails job={workspace.job} source={workspace.analyzedJobText} />
        </div>
      ) : null}
      {workspace.career ? (
        <>
          <ReadinessDetails career={workspace.career} />
          <OutcomeGroups career={workspace.career} />
          <ComparisonDetails career={workspace.career} />
        </>
      ) : null}
      <Card>
        <h2 className="font-semibold">How the number is assigned</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-slate-700 dark:text-slate-200">
          {SCORING_METHOD.map((line) => <li key={line}>{line}</li>)}
        </ul>
      </Card>
    </div>
  )
}

function OutcomeGroups({ career }: { career: CareerReport }) {
  const matches = career.comparison?.matches ?? []
  const groups = [
    ["Matched", matches.filter((item) => item.outcome === "matched")],
    ["Related, not matched", matches.filter((item) => item.outcome === "related")],
    ["Missing", matches.filter((item) => item.outcome === "missing")],
  ] as const
  if (matches.length === 0) return null
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {groups.map(([title, items]) => (
        <Card key={title}>
          <h2 className="font-semibold">{title}</h2>
          <ul className="mt-3 space-y-2 text-sm">
            {items.length === 0 ? <li className="text-slate-500">None.</li> : items.map((item, index) => (
              <li key={index} className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/70">
                <span className="font-medium">{item.requirement.skill_name || item.requirement.kind}</span>
                <p className="mt-1 text-slate-600 dark:text-slate-300">{item.note || item.requirement.text}</p>
              </li>
            ))}
          </ul>
        </Card>
      ))}
    </div>
  )
}
