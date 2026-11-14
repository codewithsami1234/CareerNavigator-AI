import { lazy, Suspense, useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { checkHealth } from "../api"
import { useAuth } from "../auth"
import { Button, Card, GlassCard, GradientHero, ProgressRing, SectionHeader, SkillBadge, StatCard } from "../components/ui"
import { groupSkills, progressKey } from "../evidence"
import { useWorkspace } from "../workspace"

const OutcomeChart = lazy(() => import("../components/OutcomeChart").then((module) => ({ default: module.OutcomeChart })))
const SkillCategoryChart = lazy(() => import("../components/SkillCategoryChart").then((module) => ({ default: module.SkillCategoryChart })))

export function Overview() {
  const workspace = useWorkspace()
  const auth = useAuth()
  const firstName = auth.user?.name.split(/\s+/).filter(Boolean)[0]
  const [health, setHealth] = useState("Checking the analysis API…")
  const [healthy, setHealthy] = useState<boolean | null>(null)

  useEffect(() => {
    let cancelled = false
    checkHealth().then((result) => {
      if (cancelled) return
      setHealthy(result.ok)
      setHealth(result.message)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const resume = workspace.resume
  const name = resume?.contact?.name
  const estimate = workspace.career?.readiness?.estimate
  const milestones = workspace.career?.roadmap?.milestones ?? []
  const done = milestones.filter((item, index) => workspace.progress[progressKey(index, item.title || "Milestone")]).length
  const comparison = workspace.career?.comparison
  const groups = groupSkills(resume?.skills ?? [])
  const paths = workspace.career?.guidance?.career_paths ?? []

  return (
    <div className="space-y-4">
      <GradientHero>
        {firstName ? <p className="text-lg font-semibold">Welcome back, {firstName}!</p> : null}
        <p className="muted mt-2 max-w-2xl text-sm leading-6">
          {resume
            ? "The figures below are copied from the latest saved analysis."
            : "No analysis is saved yet. Counts appear only after a resume is read."}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link to="/resume-analyzer" className="btn btn-primary">Analyze a resume</Link>
          {resume ? <Button variant="secondary" onClick={workspace.clearCurrent}>Clear current results</Button> : null}
        </div>
        <p className={`mt-3 text-sm ${healthy === false ? "text-[var(--danger)]" : "muted"}`}>{health}</p>
        {name ? (
          <p className="muted mt-2 text-sm">Latest extracted name: {name}. Missing names stay blank instead of being guessed.</p>
        ) : resume ? (
          <p className="muted mt-2 text-sm">A resume is stored, and no name was extracted.</p>
        ) : null}
      </GradientHero>

      {resume ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard icon="file-earmark-check" label="Resume analysis" value={resume.status || "unknown"} detail={resume.file_name || "Uploaded file"} />
          <StatCard icon="lightning-charge" label="Skills detected" value={String(resume.skills?.length ?? 0)} detail="Taxonomy matches with evidence" />
          <StatCard icon="check2-circle" label="Matched skills" value={comparison ? String(comparison.matched_count ?? 0) : "Not compared"} detail={comparison ? "From the latest comparison" : "Compare a job to fill this"} />
          <StatCard icon="exclamation-circle" label="Skill gaps" value={comparison ? String(comparison.missing_count ?? 0) : "Not compared"} detail={comparison ? `${comparison.related_count ?? 0} related, not matched` : "Related skills are not matches"} />
        </div>
      ) : null}

      {resume ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Card className="stat-card gradient-border">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--muted)]">Career readiness</p>
                <p className="stat-value">{estimate == null ? "Not calculated" : `${estimate} / 100`}</p>
                <p className="muted mt-1 text-sm">{workspace.career?.readiness?.band || "Shown only when required items can be scored"}</p>
              </div>
              {typeof estimate === "number" ? <ProgressRing value={estimate} label="Career readiness" /> : null}
            </div>
          </Card>
          <StatCard
            icon="signpost"
            label="Roadmap progress"
            value={milestones.length === 0 ? "No milestones" : `${done} / ${milestones.length}`}
            detail="Saved with your account. Not verified learning."
          />
        </div>
      ) : null}

      {resume && (groups.length > 0 || paths.length > 0 || comparison) ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {groups.length > 0 || paths.length > 0 ? (
            <GlassCard>
              <SectionHeader title="Skills overview" subtitle="Counts from the latest resume. This is not proficiency." />
              {groups.length > 0 ? (
                <ul className="mt-4 space-y-2 text-sm">
                  {groups.map(([category, skills]) => (
                    <li key={category} className="flex items-center justify-between gap-3">
                      <SkillBadge>{category}</SkillBadge>
                      <span className="muted">{skills.length}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
              {paths.length > 0 ? (
                <div className="mt-4">
                  <h3 className="text-sm font-semibold">Path labels from these skills</h3>
                  <ul className="mt-2 space-y-2 text-sm">
                    {paths.map((item) => <li key={item.title}>{item.title}. {item.reason}</li>)}
                  </ul>
                </div>
              ) : null}
            </GlassCard>
          ) : null}
          {comparison ? (
            <Card>
              <SectionHeader title="Skill gap summary" subtitle="Related skills are not counted as matches." />
              <ul className="mt-4 space-y-2 text-sm">
                <li className="warm-row flex justify-between px-3 py-2"><span>Matched</span><span>{comparison.matched_count ?? 0}</span></li>
                <li className="warm-row flex justify-between px-3 py-2"><span>Related, not matched</span><span>{comparison.related_count ?? 0}</span></li>
                <li className="warm-row flex justify-between px-3 py-2"><span>Missing</span><span>{comparison.missing_count ?? 0}</span></li>
                <li className="warm-row flex justify-between px-3 py-2"><span>Indeterminate</span><span>{comparison.indeterminate_count ?? 0}</span></li>
              </ul>
            </Card>
          ) : null}
        </div>
      ) : null}

      {resume && (resume.skills?.length ?? 0) > 0 ? (
        <Suspense fallback={<Card><p className="muted text-sm">Loading the skill chart…</p></Card>}>
          <SkillCategoryChart skills={resume.skills ?? []} />
        </Suspense>
      ) : null}

      {workspace.career ? (
        <Suspense fallback={<Card><p className="muted text-sm">Loading the comparison chart…</p></Card>}>
          <OutcomeChart career={workspace.career} />
        </Suspense>
      ) : null}

      {workspace.history.length > 0 ? (
      <Card>
        <SectionHeader title="Recent analysis activity" subtitle="Saved snapshots from this account. Resume files are not kept." />
        <ul className="mt-4 space-y-2">
            {workspace.history.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--line)] px-3 py-2 text-sm">
                <span>
                  <span className="font-medium">{item.label}</span>
                  <span className="muted"> · {item.skillCount} skills · {item.readiness == null ? "no estimate" : `${item.readiness}/100`}</span>
                </span>
                <span className="flex gap-2">
                  <Button variant="secondary" onClick={() => workspace.restore(item.id)}>Restore</Button>
                  <Button variant="ghost" onClick={() => workspace.removeSnapshot(item.id)}>Remove</Button>
                </span>
              </li>
            ))}
          </ul>
      </Card>
      ) : null}
    </div>
  )
}
