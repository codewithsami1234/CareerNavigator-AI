import { Link } from "react-router-dom"
import { GuidancePanels } from "../components/views"
import { Alert, Card, EmptyState, Field, inputClass } from "../components/ui"
import { CAREER_GOALS } from "../demo"
import { progressKey } from "../evidence"
import { useWorkspace } from "../workspace"

export function RoadmapPage() {
  const workspace = useWorkspace()
  const roadmap = workspace.career?.roadmap
  const milestones = roadmap?.milestones ?? []

  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-lg font-semibold">Career goal you selected</h2>
        <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">
          This label is stored with the report. It does not change the match calculation. Learning stages come from the job comparison. General sequencing notes are labeled when the posting did not name that prerequisite.
        </p>
        <div className="mt-4 max-w-md">
          <Field label="Target career">
            <select
              className={inputClass}
              value={workspace.targetCareer}
              onChange={(event) => workspace.setTargetCareer(event.target.value)}
            >
              <option value="">Not selected</option>
              {CAREER_GOALS.map((goal) => <option key={goal} value={goal}>{goal}</option>)}
            </select>
          </Field>
        </div>
      </Card>
      {workspace.career?.guidance ? (
        <GuidancePanels
          guidance={workspace.career.guidance}
          sections={["career_paths", "short_term", "long_term", "weekly_focus", "project_ideas", "skills_to_strengthen"]}
        />
      ) : null}
      {!workspace.career || !roadmap || roadmap.status === "unavailable" ? (
        <EmptyState
          title="No roadmap yet"
          body={roadmap?.reason || "A roadmap is sequenced from skill-gap recommendations. Compare a resume with a job description first."}
          action={<Link className="link-accent text-sm" to="/job-matcher">Open Job Matcher</Link>}
        />
      ) : (
        <>
          {workspace.careerStale ? <Alert tone="warning">Rebuild the comparison after the latest GitHub read if you want those observations in the career report. Milestones still come from the job gaps.</Alert> : null}
          {roadmap.planning_note ? <Alert tone="info">{roadmap.planning_note}</Alert> : null}
          <ol className="timeline">
            {milestones.map((item, index) => {
              const title = item.title || "Milestone"
              const key = progressKey(index, title)
              return (
                <li key={key}>
                  <Card>
                    <label className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        className="mt-1"
                        checked={workspace.progress[key] === true}
                        onChange={() => workspace.toggleProgress(key)}
                      />
                      <span>
                        <span className="font-semibold">{index + 1}. {title}</span>
                        <span className="mt-1 block text-xs uppercase tracking-wide text-slate-500">Source: {item.source || "suggestion"}</span>
                      </span>
                    </label>
                    <div className="mt-3 space-y-2 text-sm leading-6">
                      {item.objective ? <p><span className="font-medium">Objective. </span>{item.objective}</p> : null}
                      {item.practice_task ? <p><span className="font-medium">Practice. </span>{item.practice_task}</p> : null}
                      {item.demonstration ? <p><span className="font-medium">Evidence to keep. </span>{item.demonstration}</p> : null}
                      {item.posting_text ? <p><span className="font-medium">Posting text. </span>{item.posting_text}</p> : null}
                      {(item.prerequisites ?? []).length > 0 ? <p><span className="font-medium">Prerequisites. </span>{item.prerequisites?.join(", ")}</p> : null}
                    </div>
                  </Card>
                </li>
              )
            })}
          </ol>
          <Card>
            <h2 className="font-semibold">Limits of this plan</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
              {(roadmap.limitations ?? []).map((note) => <li key={note}>{note}</li>)}
            </ul>
          </Card>
        </>
      )}
    </div>
  )
}
