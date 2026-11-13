import { useEffect, useState } from "react"
import { checkHealth, csrfHeaders } from "../api"
import { Alert, Button, Card, Field, inputClass } from "../components/ui"
import { CAREER_GOALS } from "../demo"
import { AccountPanel } from "./AuthPages"
import { useWorkspace } from "../workspace"

export function SettingsPage() {
  const workspace = useWorkspace()
  const [confirming, setConfirming] = useState<"analysis" | "history" | null>(null)
  const [health, setHealth] = useState("Checking the analysis API…")

  useEffect(() => {
    let cancelled = false
    checkHealth().then((result) => {
      if (!cancelled) setHealth(result.message)
    })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="space-y-4">
      <AccountPanel />
      <Card>
        <h2 className="text-lg font-semibold">Appearance</h2>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">The choice is saved with your account.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant={workspace.theme === "light" ? "primary" : "secondary"} onClick={() => workspace.setTheme("light")}>Light</Button>
          <Button variant={workspace.theme === "dark" ? "primary" : "secondary"} onClick={() => workspace.setTheme("dark")}>Dark</Button>
        </div>
      </Card>
      <Card>
        <h2 className="font-semibold">API connection</h2>
        <p className="mt-2 text-sm leading-6">{health}</p>
      </Card>
      <Card>
        <h2 className="text-lg font-semibold">Saved analysis</h2>
        <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
          Results are saved with your account. Another person signed in on this browser does not see them. Deleting the analysis removes it from your account.
        </p>
        <div className="mt-4 grid max-w-xl gap-4">
          <Field label="Target career" hint="A label for the report. It does not change scores.">
            <select className={inputClass} value={workspace.targetCareer} onChange={(event) => workspace.setTargetCareer(event.target.value)}>
              <option value="">Not selected</option>
              {CAREER_GOALS.map((goal) => <option key={goal}>{goal}</option>)}
            </select>
          </Field>
          <Field label="Weekly hours" hint="A positive whole number adds a planning note. It does not set how long a milestone takes. Leave blank to omit it.">
            <input className={inputClass} inputMode="numeric" value={workspace.weeklyHours} onChange={(event) => workspace.setWeeklyHours(event.target.value)} />
          </Field>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-1" checked={workspace.useOcr} onChange={(event) => workspace.setUseOcr(event.target.checked)} />
            <span>Default the resume form to OCR for scanned PDFs and resume images.</span>
          </label>
        </div>
      </Card>
      {workspace.persistWarning ? <Alert tone="warning">{workspace.persistWarning}</Alert> : null}
      <Card>
        <h2 className="font-semibold">Delete saved analysis</h2>
        <p className="mt-2 text-sm leading-6">Deleting the analysis removes the current workspace and its history, including extracted resume text. Clearing history removes older snapshots and leaves the current screen. Neither action changes Python project files.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="secondary" onClick={workspace.clearCurrent}>Clear current results</Button>
          {confirming === "history" ? (
            <Button variant="danger" onClick={() => { workspace.history.forEach((item) => workspace.removeSnapshot(item.id)); setConfirming(null) }}>Confirm clear history</Button>
          ) : (
            <Button variant="secondary" onClick={() => setConfirming("history")}>Clear application history</Button>
          )}
          {confirming === "analysis" ? (
            <Button variant="danger" onClick={() => {
              workspace.clearAll()
              void fetch("/api/records", { method: "DELETE", credentials: "include", headers: csrfHeaders() })
              setConfirming(null)
            }}>Confirm delete</Button>
          ) : (
            <Button variant="danger" onClick={() => setConfirming("analysis")}>Delete saved analysis</Button>
          )}
          {confirming ? <Button variant="ghost" onClick={() => setConfirming(null)}>Cancel</Button> : null}
        </div>
      </Card>
    </div>
  )
}
