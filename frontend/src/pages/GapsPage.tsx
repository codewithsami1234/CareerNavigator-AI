import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { GuidancePanels } from "../components/views"
import { Alert, Card, EmptyState, inputClass } from "../components/ui"
import type { Recommendation, RequirementMatch } from "../types"
import { useWorkspace } from "../workspace"

function labelOf(match: RequirementMatch) {
  const requirement = match.requirement
  return requirement.skill_name || requirement.certification_name || requirement.degree_level || requirement.kind || requirement.text || "Requirement"
}

export function GapsPage() {
  const { career, careerStale, resume } = useWorkspace()
  const [query, setQuery] = useState("")
  const [kind, setKind] = useState("all")
  const [selected, setSelected] = useState<RequirementMatch | null>(null)

  const matches = career?.comparison?.matches ?? []
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return matches.filter((match) => {
      if (kind !== "all" && match.requirement.kind !== kind) return false
      if (!needle) return true
      return `${labelOf(match)} ${match.requirement.text ?? ""} ${match.outcome ?? ""}`.toLowerCase().includes(needle)
    })
  }, [matches, query, kind])

  if (!career) {
    return (
      <EmptyState
        title="No comparison yet"
        body="Skill gaps are the missing and related requirements from a resume-to-job comparison. Related skills are not treated as matches. Analyze a resume, paste a job description, and choose Compare with resume."
        action={<Link className="link-accent text-sm" to="/job-matcher">Open Job Matcher</Link>}
      />
    )
  }

  const buckets = {
    matched: filtered.filter((item) => item.outcome === "matched"),
    missing: filtered.filter((item) => item.outcome === "missing"),
    related: filtered.filter((item) => item.outcome === "related"),
    other: filtered.filter((item) => !["matched", "missing", "related"].includes(item.outcome || "")),
  }
  const kinds = [...new Set(matches.map((item) => item.requirement.kind).filter(Boolean))] as string[]

  return (
    <div className="space-y-4">
      {careerStale ? <Alert tone="warning">This gap list was built before the latest GitHub read. Rebuild the comparison if you want repository observations included. They do not change which requirements matched.</Alert> : null}
      {career.guidance ? <GuidancePanels guidance={career.guidance} sections={["partially_supported", "skills_to_strengthen"]} /> : null}
      <Card>
        <h2 className="text-lg font-semibold">Filter the comparison</h2>
        <p className="mt-1 text-sm text-slate-500">Counts below are the rows that match the search. They are not a separate score.</p>
        <div className="mt-4 grid gap-3 md:grid-cols-[1fr_12rem]">
          <label className="text-sm font-medium">
            Search
            <input className={`${inputClass} mt-2`} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Skill or requirement text" />
          </label>
          <label className="text-sm font-medium">
            Category
            <select className={`${inputClass} mt-2`} value={kind} onChange={(event) => setKind(event.target.value)}>
              <option value="all">All kinds</option>
              {kinds.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
        </div>
      </Card>
      <Card>
        <h2 className="font-semibold">Current resume skills</h2>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{(resume?.skills ?? []).map((skill) => skill.name).join(", ") || "No skills were extracted."}</p>
      </Card>
      <div className="grid gap-4 lg:grid-cols-3">
        <Bucket title="Matched" note="Evidence was found." items={buckets.matched} onSelect={setSelected} />
        <Bucket title="Missing" note="No supporting evidence was found." items={buckets.missing} onSelect={setSelected} />
        <Bucket title="Related, not matched" note="A related skill does not satisfy the requirement." items={buckets.related} onSelect={setSelected} />
      </div>
      {buckets.other.length > 0 ? <Bucket title="Indeterminate or other" note="The text did not support a yes or no." items={buckets.other} onSelect={setSelected} /> : null}
      {selected ? (
        <Card>
          <h2 className="font-semibold">{labelOf(selected)}</h2>
          <p className="mt-2 text-sm">Outcome: {selected.outcome}. Priority: {selected.requirement.priority}. Kind: {selected.requirement.kind}.</p>
          <p className="mt-2 text-sm">Posting: {selected.requirement.text}</p>
          {selected.note ? <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{selected.note}</p> : null}
          {(selected.evidence ?? []).map((item, index) => (
            <p key={index} className="mt-2 text-sm">Evidence [{item.section}, {item.evidence_type}]: {item.text}</p>
          ))}
          {(selected.related_skills ?? []).length > 0 ? <p className="mt-2 text-sm">Related skills, not counted as a match: {selected.related_skills?.join(", ")}</p> : null}
        </Card>
      ) : null}
      <Card>
        <h2 className="font-semibold">Priority recommendations</h2>
        <p className="mt-1 text-sm text-slate-500">Taken from the pipeline recommendation list. A higher listing is the pipeline’s order, not a percentage.</p>
        <RecommendationBlock items={career.recommendations?.items ?? []} />
        <RecommendationBlock items={career.recommendations?.experience_gaps ?? []} />
        {career.recommendations?.status === "unavailable" ? <p className="mt-3 text-sm">{career.recommendations.reason}</p> : null}
      </Card>
    </div>
  )
}

function Bucket({
  title,
  note,
  items,
  onSelect,
}: {
  title: string
  note: string
  items: RequirementMatch[]
  onSelect: (item: RequirementMatch) => void
}) {
  return (
    <Card>
      <h2 className="font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-slate-500">{note} {items.length} shown.</p>
      <ul className="mt-3 max-h-80 space-y-2 overflow-auto text-sm">
        {items.length === 0 ? <li className="text-slate-500">None in this filter.</li> : items.map((item, index) => (
          <li key={`${labelOf(item)}-${index}`}>
            <button type="button" className="min-h-11 w-full rounded-xl border border-[var(--line)] px-3 py-2 text-left hover:bg-white/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--gold-deep)]" onClick={() => onSelect(item)}>
              <span className="font-medium">{labelOf(item)}</span>
              <span className="mt-1 block text-slate-500">{item.requirement.priority} · {item.requirement.kind}</span>
            </button>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function RecommendationBlock({ items }: { items: Recommendation[] }) {
  if (items.length === 0) return null
  return (
    <ul className="mt-3 space-y-2 text-sm">
      {items.map((item, index) => (
        <li key={`${item.skill_name}-${index}`} className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/70">
          <span className="font-medium">{item.skill_name}</span>
          <span className="text-slate-500"> · {item.gap_kind} · priority {item.priority}</span>
          <p className="mt-1">{item.reason}</p>
          {item.posting_text ? <p className="mt-1 text-slate-500">Posting: {item.posting_text}</p> : null}
        </li>
      ))}
    </ul>
  )
}
