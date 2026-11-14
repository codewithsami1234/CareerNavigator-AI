import { useState } from "react"
import { analyzeGithub, pipelineProblem } from "../api"
import { GithubDetails } from "../components/views"
import { Alert, Button, Card, Field, inputClass } from "../components/ui"
import { compareSkillEvidence } from "../evidence"
import { useWorkspace } from "../workspace"

export function GithubPage() {
  const workspace = useWorkspace()
  const [username, setUsername] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onRead() {
    if (!username.trim()) {
      setError("Enter a GitHub username or a https://github.com/username profile URL.")
      return
    }
    setLoading(true)
    setError(null)
    try {
      const analysis = await analyzeGithub(username.trim())
      workspace.setGithub(analysis)
      const problem = pipelineProblem(analysis)
      if (analysis.status === "rate_limited") {
        setError(analysis.errors?.[0] || analysis.reason || "GitHub rate-limited this request. The resume and job results are unchanged.")
      } else if (problem) {
        setError(problem)
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "GitHub could not be read.")
    } finally {
      setLoading(false)
    }
  }

  const resumeNames = (workspace.resume?.skills ?? []).map((skill) => skill.name)
  const githubNames = (workspace.github?.skills ?? []).map((skill) => skill.skill_name || "").filter(Boolean)
  const overlap = workspace.resume && workspace.github?.status === "success"
    ? compareSkillEvidence(resumeNames, githubNames)
    : null

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-lg font-semibold">Public GitHub profile</h2>
        <p className="muted mt-1 text-sm leading-6">
          No GitHub password is requested. A rate limit, missing user, or network error is shown here and does not discard the resume.
        </p>
        <div className="mt-4 grid gap-3">
          <Field label="Username or profile URL" hint="Repository URLs are rejected. Example: octocat">
            <input className={inputClass} value={username} onChange={(event) => setUsername(event.target.value)} />
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => void onRead()} disabled={loading}>{loading ? "Reading GitHub…" : "Read profile"}</Button>
            <Button variant="secondary" onClick={() => setUsername("octocat")}>Use octocat</Button>
          </div>
        </div>
      </Card>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {workspace.github ? <GithubDetails github={workspace.github} /> : null}
      {overlap ? (
        <Card>
          <h2 className="font-semibold">Resume names also seen in the scanned metadata</h2>
          <p className="mt-2 text-sm leading-6">{overlap.note}</p>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <NameColumn title="In both results" names={overlap.supported} empty="No shared taxonomy names." />
            <NameColumn title="Resume only" names={overlap.resumeOnly} empty="Every extracted resume skill was also observed, or the resume had no skills." />
            <NameColumn title="GitHub only" names={overlap.githubOnly} empty="No extra taxonomy names were observed." />
          </div>
        </Card>
      ) : null}
    </div>
  )
}

function NameColumn({ title, names, empty }: { title: string; names: string[]; empty: string }) {
  return (
    <div>
      <h3 className="text-sm font-semibold">{title}</h3>
      {names.length === 0 ? <p className="mt-2 text-sm text-slate-500">{empty}</p> : (
        <ul className="mt-2 space-y-1 text-sm">
          {names.map((name) => <li key={name}>{name}</li>)}
        </ul>
      )}
    </div>
  )
}
