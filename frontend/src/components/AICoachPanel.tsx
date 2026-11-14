import { useState } from "react"
import { askAICoach } from "../api"
import type { AICoachResult } from "../types"
import { parseWeeklyHours, useWorkspace } from "../workspace"
import { Alert, Button, Card } from "./ui"

/** Optional LLM explanations and interview practice for the current roadmap. */
export function AICoachPanel() {
  const workspace = useWorkspace()
  const [result, setResult] = useState<AICoachResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    if (!workspace.resume) return
    const hours = parseWeeklyHours(workspace.weeklyHours)
    setLoading(true)
    setError(null)
    try {
      setResult(await askAICoach({
        resume: workspace.resume,
        job: workspace.job,
        github: workspace.github,
        weeklyHours: hours.hours,
        targetCareer: workspace.targetCareer,
      }))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The AI Coach could not be reached.")
    } finally {
      setLoading(false)
    }
  }

  const ok = result?.status === "success"

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">AI Coach</h2>
          <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
            Plain-language explanations of each milestone and interview questions for your skill gaps. Only skill and roadmap data is sent, never your name or contact details.
          </p>
        </div>
        <Button onClick={run} disabled={loading || !workspace.resume}>
          {loading ? "Thinking…" : ok ? "Regenerate" : "Ask AI Coach"}
        </Button>
      </div>

      {error ? <div className="mt-4"><Alert tone="error">{error}</Alert></div> : null}
      {result && !ok ? (
        <div className="mt-4">
          <Alert tone={result.status === "unavailable" ? "info" : "warning"}>{result.reason || "The AI Coach has no answer right now."}</Alert>
        </div>
      ) : null}

      {ok ? (
        <div className="mt-4 space-y-5 text-sm leading-6">
          {result.summary ? <p className="text-base">{result.summary}</p> : null}

          {(result.milestones ?? []).length > 0 ? (
            <div>
              <h3 className="font-semibold">Why each milestone matters</h3>
              <ul className="mt-2 space-y-3">
                {result.milestones?.map((item) => (
                  <li key={item.title}>
                    <p className="font-medium">{item.title}</p>
                    <p>{item.why_it_matters}</p>
                    {(item.tips ?? []).length > 0 ? (
                      <ul className="mt-1 list-disc pl-5 text-slate-600 dark:text-slate-300">
                        {item.tips?.map((tip) => <li key={tip}>{tip}</li>)}
                      </ul>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {(result.interview_questions ?? []).length > 0 ? (
            <div>
              <h3 className="font-semibold">Interview practice</h3>
              <ol className="mt-2 list-decimal space-y-3 pl-5">
                {result.interview_questions?.map((item, index) => (
                  <li key={`${index}-${item.question}`}>
                    <p>
                      {item.skill ? <span className="mr-2 text-xs uppercase tracking-wide text-slate-500">{item.skill}</span> : null}
                      {item.question}
                    </p>
                    {item.good_answer_covers ? (
                      <details className="mt-1">
                        <summary className="cursor-pointer text-slate-600 dark:text-slate-300">What a strong answer covers</summary>
                        <p className="mt-1">{item.good_answer_covers}</p>
                      </details>
                    ) : null}
                  </li>
                ))}
              </ol>
            </div>
          ) : null}

          <p className="text-xs text-slate-500">
            {result.disclaimer}{result.model ? ` Model: ${result.model}.` : ""}
          </p>
        </div>
      ) : null}
    </Card>
  )
}
