import { useState } from "react"
import { Link } from "react-router-dom"
import { buildReport } from "../api"
import { Alert, Button, Card, EmptyState } from "../components/ui"
import { appendBrowserProgress, downloadBase64, downloadText, sliceReport } from "../evidence"
import { parseWeeklyHours, useWorkspace } from "../workspace"

export function ReportsPage() {
  const workspace = useWorkspace()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [markdown, setMarkdown] = useState<string | null>(null)
  const [skillsCsv, setSkillsCsv] = useState<string | null>(null)
  const [comparisonCsv, setComparisonCsv] = useState<string | null>(null)
  const [jsonText, setJsonText] = useState<string | null>(null)
  const [pdfBase64, setPdfBase64] = useState<string | null>(null)
  const [previewId, setPreviewId] = useState("resume")

  async function onBuild() {
    if (!workspace.resume) {
      setError("Analyze a resume before building a report.")
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
      const bundle = await buildReport({
        resume: workspace.resume,
        job: workspace.job,
        github: workspace.github,
        weeklyHours: hours.hours,
        jobTitle: workspace.jobTitle,
        company: workspace.company,
        targetCareer: workspace.targetCareer,
      })
      const career = bundle.report?.career_report
      if (career) workspace.setCareer(career)
      const base = bundle.markdown || ""
      const withProgress = appendBrowserProgress(base, career?.roadmap?.milestones ?? [], workspace.progress)
      setMarkdown(withProgress)
      setSkillsCsv(bundle.skills_csv ?? null)
      setComparisonCsv(bundle.comparison_csv ?? null)
      setJsonText(JSON.stringify(bundle.report ?? {}, null, 2))
      setPdfBase64(bundle.pdf_base64 ?? null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The report could not be built.")
    } finally {
      setLoading(false)
    }
  }

  if (!workspace.resume) {
    return (
      <EmptyState
        title="Nothing to export"
        body="Reports are built from an analysis already returned by the API. Upload a resume first. Job, GitHub, and roadmap sections appear when those results exist."
        action={<Link className="link-accent text-sm" to="/resume-analyzer">Open Resume Analyzer</Link>}
      />
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-lg font-semibold">Download this analysis</h2>
        <p className="muted mt-1 text-sm leading-6">
          The file is assembled from the saved analysis. Checked roadmap items are labeled as unverified.
        </p>
        <Button className="mt-4" onClick={() => void onBuild()} disabled={loading}>{loading ? "Building report…" : "Build report"}</Button>
      </Card>
      {error ? <Alert tone="error">{error}</Alert> : null}
      <div className="grid gap-4 md:grid-cols-2">
        {sliceReport(markdown ?? "").map((slice) => (
          <Card key={slice.id}>
            <h2 className="font-semibold">{slice.title}</h2>
            <p className="mt-2 text-sm text-slate-500">
              {slice.markdown ? "Included in the latest pipeline report." : "Generate the report. This section appears only if the pipeline returned it."}
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button variant="secondary" disabled={!slice.markdown} onClick={() => setPreviewId(slice.id)}>Preview</Button>
              <Button variant="secondary" disabled={!slice.markdown} onClick={() => downloadText(`${slice.id}-report.md`, slice.markdown, "text/markdown")}>Download</Button>
            </div>
          </Card>
        ))}
      </div>
      {markdown ? (
        <Card>
          <h2 className="font-semibold">Full report</h2>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button onClick={() => downloadText("careernavigator-report.md", markdown, "text/markdown")}>Markdown</Button>
            <Button variant="secondary" onClick={() => downloadBase64("careernavigator-report.pdf", pdfBase64 || "", "application/pdf")} disabled={!pdfBase64}>PDF</Button>
            <Button variant="secondary" onClick={() => downloadText("careernavigator-report.json", jsonText || "{}", "application/json")} disabled={!jsonText}>JSON</Button>
            <Button variant="secondary" onClick={() => downloadText("skills.csv", skillsCsv || "", "text/csv")} disabled={!skillsCsv}>Skills CSV</Button>
            <Button variant="secondary" onClick={() => downloadText("comparison.csv", comparisonCsv || "", "text/csv")} disabled={!comparisonCsv}>Comparison CSV</Button>
          </div>
          <pre className="mt-4 max-h-96 overflow-auto whitespace-pre-wrap rounded-xl bg-slate-50 p-4 text-xs leading-5 dark:bg-slate-950">
            {sliceReport(markdown).find((slice) => slice.id === previewId)?.markdown || markdown}
          </pre>
        </Card>
      ) : null}
    </div>
  )
}
