import { groupSkills } from "../evidence"
import type {
  CareerGuidance,
  CareerReport,
  ContactInfo,
  GitHubAnalysis,
  GitHubRepository,
  GuidanceItem,
  JobAnalysis,
  Recommendation,
  ResumeAnalysis,
} from "../types"
import { BulletList, Card, StatusBadge } from "./ui"

const CONTACT: { key: keyof ContactInfo; label: string }[] = [
  { key: "name", label: "Name" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Phone" },
  { key: "location", label: "Location" },
  { key: "linkedin", label: "LinkedIn" },
  { key: "github", label: "GitHub" },
  { key: "leetcode", label: "LeetCode" },
  { key: "twitter", label: "X / Twitter" },
]

function requirementLabel(requirement: { skill_name?: string | null; certification_name?: string | null; degree_level?: string | null; kind?: string; text?: string }) {
  return requirement.skill_name || requirement.certification_name || requirement.degree_level || requirement.kind || requirement.text || "Requirement"
}

export function ResumeDetails({ resume }: { resume: ResumeAnalysis }) {
  const groups = groupSkills(resume.skills ?? [])
  const missing = CONTACT.filter((field) => !resume.contact?.[field.key]).map((field) => field.label)
  const provenance = resume.text_provenance ?? []
  const findings = resume.quality_report?.findings ?? []

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold">Extracted resume</h2>
          <StatusBadge status={resume.status} />
        </div>
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <div><dt className="text-slate-500">File</dt><dd>{resume.file_name || "—"}</dd></div>
          <div><dt className="text-slate-500">Format</dt><dd>{resume.source_format || "—"}</dd></div>
          <div><dt className="text-slate-500">Pages</dt><dd>{resume.page_count ?? "—"}</dd></div>
          <div><dt className="text-slate-500">Text length</dt><dd>{resume.text_length ?? "—"}</dd></div>
        </dl>
        {resume.status === "partial" ? (
          <p className="mt-3 text-sm text-amber-800 dark:text-amber-200">Text was recovered, but little structure was detected. Blank fields below were not inferred.</p>
        ) : null}
      </Card>

      <Card>
        <h3 className="font-semibold">Where the text came from</h3>
        {provenance.length === 0 ? (
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">No provenance records were returned. Native PDF, DOCX, and TXT analysis omits this list unless the document path ran.</p>
        ) : (
          <ul className="mt-3 space-y-2 text-sm">
            {provenance.map((item, index) => (
              <li key={`${item.method}-${index}`}>
                Page {item.page_number ?? "—"}: <strong>{item.method}</strong>, {item.char_count ?? 0} characters
                {item.confidence != null ? `, OCR confidence ${item.confidence}` : ""}
                {item.suppressed_duplicate ? " (duplicate suppressed)" : ""}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <h3 className="font-semibold">Document quality</h3>
        {findings.length === 0 ? (
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">No quality findings were returned for this file.</p>
        ) : (
          <ul className="mt-3 space-y-2 text-sm">
            {findings.map((finding, index) => (
              <li key={`${finding.code}-${index}`} className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/70">
                <span className="font-medium">{finding.severity}</span>
                {finding.kind ? ` · ${finding.kind}` : ""} — {finding.message}
              </li>
            ))}
          </ul>
        )}
        <BulletList items={resume.quality_report?.limitations} empty="" />
      </Card>

      <Card>
        <h3 className="font-semibold">Contact extracted from the file</h3>
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          {CONTACT.filter((field) => resume.contact?.[field.key]).map((field) => (
            <div key={field.key}>
              <dt className="text-slate-500">{field.label}</dt>
              <dd>{resume.contact?.[field.key]}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">Not found in the extracted text: {missing.join(", ")}. These were not filled in.</p>
      </Card>

      <Card>
        <h3 className="font-semibold">Skills by category</h3>
        <p className="mt-1 text-sm text-slate-500">Evidence type is “used” when the skill appears in experience or projects, otherwise “mentioned”. Proficiency is not inferred.</p>
        {groups.length === 0 ? <p className="mt-3 text-sm">No taxonomy skills were extracted.</p> : (
          <div className="mt-4 space-y-4">
            {groups.map(([category, skills]) => (
              <div key={category}>
                <h4 className="gold-figure text-sm font-semibold">{category}</h4>
                <ul className="mt-2 space-y-2">
                  {skills.map((skill) => (
                    <li key={skill.name} className="rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700">
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <span className="font-medium">{skill.name}</span>
                        <span className="text-slate-500">{skill.evidence_type} · {skill.mention_count ?? 0} line(s)</span>
                      </div>
                      {(skill.evidence ?? []).map((item, index) => (
                        <p key={index} className="mt-1 text-slate-600 dark:text-slate-300">[{item.section}] {item.text}</p>
                      ))}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </Card>

      <FactList title="Education" empty="No education entries were extracted." rows={(resume.education ?? []).map((item) => item.raw_text || [item.degree, item.field_of_study, item.institution].filter(Boolean).join(", ") || "Education entry")} />
      <FactList title="Experience" empty="No experience entries were extracted." rows={(resume.experience ?? []).map((item) => item.raw_text || [item.title, item.organization, item.start_date, item.end_date].filter(Boolean).join(" · ") || "Experience entry")} />
      <FactList title="Projects" empty="No projects were extracted." rows={(resume.projects ?? []).map((item) => item.raw_text || item.name || "Project")} />
      <FactList title="Certifications and courses" empty="No certifications or courses were extracted." rows={(resume.certifications ?? []).map((item) => item.raw_text || item.name || item.kind || "Certification")} />

      <Card>
        <h3 className="font-semibold">Extracted sections</h3>
        {(resume.sections ?? []).length === 0 ? <p className="mt-2 text-sm">No sections were detected.</p> : (
          <div className="mt-3 space-y-2">
            {(resume.sections ?? []).map((section) => (
              <details key={`${section.name}-${section.heading}`} className="rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-700">
                <summary className="cursor-pointer text-sm font-medium">{section.heading || section.name}</summary>
                <pre className="mt-2 whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-200">{section.content || "(empty)"}</pre>
              </details>
            ))}
          </div>
        )}
      </Card>
      <Card>
        <h3 className="font-semibold">Warnings and errors</h3>
        <div className="mt-3 space-y-3">
          <BulletList items={resume.warnings} empty="No warnings were returned." />
          <BulletList items={resume.errors} empty="No errors were returned." />
        </div>
      </Card>
    </div>
  )
}

function FactList({ title, rows, empty }: { title: string; rows: string[]; empty: string }) {
  return (
    <Card>
      <h3 className="font-semibold">{title}</h3>
      <div className="mt-3"><BulletList items={rows} empty={empty} /></div>
    </Card>
  )
}

export function JobDetails({ job, source = "" }: { job: JobAnalysis; source?: string }) {
  const requirements = job.requirements ?? []
  const unlabeled = requirements.length > 0 && requirements.every((item) => item.priority !== "required" && item.priority !== "preferred")
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold">Requirements read from the text you supplied</h2>
        <StatusBadge status={job.status} />
      </div>
      {source.trim() ? (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer font-medium">Description that was read ({job.text_length ?? source.trim().length} characters)</summary>
          <p className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg border border-[var(--line)] bg-[var(--elevated)] px-3 py-2">{source}</p>
        </details>
      ) : job.status === "success" || job.status === "partial" ? (
        <p className="mt-3 text-sm">This result was saved before the description text was kept with it. Read the description again to attach the text to these requirements.</p>
      ) : null}
      {unlabeled ? (
        <p className="mt-3 text-sm leading-6">
          These items were found in the description. None is labeled required or preferred, so a readiness number is not calculated. Matched and missing skills still come from the comparison. They are not treated as required failures.
        </p>
      ) : null}
      {job.reason ? <p className="mt-3 text-sm">{job.reason}</p> : null}
      <ul className="mt-4 space-y-2 text-sm">
        {requirements.map((item, index) => (
          <li key={index} className="rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-700">
            <span className="font-medium">{requirementLabel(item)}</span>
            <span className="text-slate-500"> · {item.priority} · {item.kind}</span>
            <p className="mt-1 text-slate-700 dark:text-slate-200">{item.text}</p>
            {item.note ? <p className="mt-1 text-slate-500">{item.note}</p> : null}
          </li>
        ))}
      </ul>
      {requirements.length === 0 ? (
        <p className="mt-3 text-sm leading-6">No requirements were extracted. Names that are not in the skill taxonomy are not added as skills, and no readiness score is invented for them.</p>
      ) : null}
    </Card>
  )
}

export function ComparisonDetails({ career }: { career: CareerReport }) {
  const comparison = career.comparison
  if (!comparison) return <Card><h2 className="font-semibold">Comparison</h2><p className="mt-2 text-sm">No comparison was produced.</p></Card>
  return (
    <Card>
      <h2 className="text-lg font-semibold">Why each requirement landed where it did</h2>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
        Matched {comparison.matched_count ?? 0} · Related {comparison.related_count ?? 0} · Missing {comparison.missing_count ?? 0} · Indeterminate {comparison.indeterminate_count ?? 0}. Related is not counted as a match.
      </p>
      <ul className="mt-4 space-y-3 text-sm">
        {(comparison.matches ?? []).map((match, index) => (
          <li key={index} className="rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-700">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={match.outcome} />
              <span className="font-medium">{requirementLabel(match.requirement)}</span>
              <span className="text-slate-500">{match.requirement.priority}</span>
            </div>
            <p className="mt-2">{match.requirement.text}</p>
            {match.note ? <p className="mt-1 text-slate-500">{match.note}</p> : null}
            {(match.evidence ?? []).map((item, evidenceIndex) => (
              <p key={evidenceIndex} className="mt-1 text-slate-600 dark:text-slate-300">Evidence [{item.section}, {item.evidence_type}]: {item.text}</p>
            ))}
            {(match.support ?? []).map((line) => <p key={line} className="mt-1">Support: {line}</p>)}
            {(match.related_skills ?? []).length > 0 ? <p className="mt-1">Related, not matched: {match.related_skills?.join(", ")}</p> : null}
          </li>
        ))}
      </ul>
    </Card>
  )
}

export function ReadinessDetails({ career }: { career: CareerReport }) {
  const readiness = career.readiness
  if (!readiness) return null
  return (
    <Card>
      <h2 className="text-lg font-semibold">Readiness estimate</h2>
      <p className="mt-2 text-sm leading-6">{readiness.disclaimer}</p>
      <p className="gold-figure mt-4 text-4xl font-semibold tracking-tight">
        {readiness.estimate == null ? "Not scored" : `${readiness.estimate}`}
        {readiness.estimate == null ? null : <span className="text-lg font-medium text-slate-500"> / 100</span>}
      </p>
      <p className="mt-1 text-sm text-slate-500">{readiness.band}</p>
      <p className="mt-3 text-sm leading-6">{readiness.summary}</p>
      <ul className="mt-4 space-y-2 text-sm">
        {(readiness.criteria ?? []).map((item, index) => (
          <li key={`${item.name}-${index}`} className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/70">
            <span className="font-medium">{item.name}</span> — {item.status}, {item.priority}, credit {item.credit ?? 0}
            {item.scored ? ", in the denominator" : ", not scored"}
            {item.detail ? <span className="mt-1 block text-slate-600 dark:text-slate-300">{item.detail}</span> : null}
          </li>
        ))}
      </ul>
    </Card>
  )
}

function RecommendationList({ title, items }: { title: string; items: Recommendation[] }) {
  if (items.length === 0) return null
  return (
    <div className="mt-4">
      <h3 className="font-semibold">{title}</h3>
      <ul className="mt-2 space-y-3 text-sm">
        {items.map((item, index) => (
          <li key={`${item.skill_name}-${index}`} className="rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-700">
            <p className="font-medium">{item.skill_name} <span className="font-normal text-slate-500">({item.gap_kind}, {item.priority})</span></p>
            <p className="mt-1">{item.reason}</p>
            {item.posting_text ? <p className="mt-1 text-slate-500">Posting: {item.posting_text}</p> : null}
            {item.practice_task ? <p className="mt-1">Practice: {item.practice_task}</p> : null}
            {(item.prerequisites ?? []).length > 0 ? <p className="mt-1">Local prerequisites, not necessarily named in the posting: {item.prerequisites?.join(", ")}</p> : null}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function GapDetails({ career }: { career: CareerReport }) {
  const report = career.recommendations
  return (
    <Card>
      <h2 className="text-lg font-semibold">Skill gaps from this comparison</h2>
      {report?.status === "unavailable" || !report ? (
        <p className="mt-2 text-sm">{report?.reason || "No role-specific gaps were calculated."}</p>
      ) : (
        <>
          {(report.matched_skills ?? []).length > 0 ? <p className="mt-3 text-sm">Matched skills: {report.matched_skills?.join(", ")}.</p> : null}
          <RecommendationList title="Skill suggestions" items={report.items ?? []} />
          <RecommendationList title="Experience gaps" items={report.experience_gaps ?? []} />
          <div className="mt-4"><BulletList items={report.limitations} empty="" /></div>
        </>
      )}
    </Card>
  )
}

export function GithubDetails({ github }: { github: GitHubAnalysis }) {
  const names = [...new Set((github.skills ?? []).map((skill) => skill.skill_name).filter(Boolean))]
  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold">Public profile</h2>
          <StatusBadge status={github.status} />
        </div>
        {github.reason ? <p className="mt-3 text-sm">{github.reason}</p> : null}
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <div><dt className="text-slate-500">Username</dt><dd>{github.username || "—"}</dd></div>
          <div><dt className="text-slate-500">Name</dt><dd>{github.name || "Not returned"}</dd></div>
          <div><dt className="text-slate-500">Public repositories on the profile</dt><dd>{github.public_repos ?? "—"}</dd></div>
          <div><dt className="text-slate-500">Profile</dt><dd>{github.profile_url ? <a className="underline" href={github.profile_url} target="_blank" rel="noreferrer">{github.profile_url}</a> : "—"}</dd></div>
        </dl>
        {github.bio ? <p className="mt-3 text-sm">{github.bio}</p> : null}
        <div className="mt-4 space-y-3">
          <BulletList items={github.errors} empty="No errors were returned." />
          <BulletList items={github.warnings} empty="" />
          <BulletList items={github.limitations} empty="" />
        </div>
      </Card>
      <Card>
        <h3 className="font-semibold">Taxonomy skills observed in public metadata</h3>
        <p className="mt-1 text-sm text-slate-500">A language listed on a repository is not, by itself, treated as a skill. Only taxonomy matches from descriptions, topics, languages, and README excerpts are listed, and each row stays tied to a repository.</p>
        {names.length === 0 ? <p className="mt-3 text-sm">No taxonomy skills were observed in the scanned metadata.</p> : (
          <ul className="mt-3 space-y-2 text-sm">
            {(github.skills ?? []).map((skill, index) => (
              <li key={`${skill.skill_name}-${index}`} className="rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/70">
                <span className="font-medium">{skill.skill_name}</span> in {skill.repository} ({skill.source_field})
                {skill.text ? <span className="mt-1 block text-slate-600 dark:text-slate-300">{skill.text}</span> : null}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card>
        <h3 className="font-semibold">Repositories read</h3>
        <p className="mt-1 text-sm text-slate-500">At most eight recently pushed public non-fork repositories. Private repositories are not accessible. Source code is not downloaded.</p>
        {(github.repositories ?? []).length === 0 ? <p className="mt-3 text-sm">No repositories were returned.</p> : (
          <ul className="mt-3 space-y-3 text-sm">
            {(github.repositories ?? []).map((repo) => (
              <li key={repo.url || repo.name} className="rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-700">
                {repo.url ? <a className="font-medium underline" href={repo.url} target="_blank" rel="noreferrer">{repo.name}</a> : <span className="font-medium">{repo.name}</span>}
                {repo.description ? <p className="mt-1">{repo.description}</p> : null}
                <p className="mt-1 text-slate-500">Languages: {(repo.languages ?? []).join(", ") || "none listed"}</p>
                <p className="text-slate-500">Last push recorded by GitHub: {repo.pushed_at || "not returned"}</p>
                {(repo.topics ?? []).length > 0 ? <p className="text-slate-500">Topics: {repo.topics?.join(", ")}</p> : null}
                {repo.readme_excerpt ? <p className="mt-1 text-slate-600 dark:text-slate-300">README excerpt: {repo.readme_excerpt}</p> : null}
              </li>
            ))}
          </ul>
        )}
      </Card>
      {github.status === "success" ? <LanguageSummary repositories={github.repositories ?? []} /> : null}
    </div>
  )
}

function LanguageSummary({ repositories }: { repositories: GitHubRepository[] }) {
  const counts = new Map<string, number>()
  for (const repo of repositories) {
    for (const language of repo.languages ?? []) {
      counts.set(language, (counts.get(language) ?? 0) + 1)
    }
  }
  const rows = [...counts.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
  return (
    <Card>
      <h3 className="font-semibold">Languages named on the repositories that were read</h3>
      <p className="mt-1 text-sm text-slate-500">Each count is how many of those repositories list the language. It is not a byte count, a proficiency score, or a review of the source.</p>
      {rows.length === 0 ? <p className="mt-3 text-sm">No languages were returned.</p> : (
        <ul className="mt-3 space-y-2 text-sm">
          {rows.map(([language, count]) => (
            <li key={language} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/70">
              <span>{language}</span>
              <span className="text-slate-500">{count} {count === 1 ? "repository" : "repositories"}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

export function GuidancePanels({
  guidance,
  sections,
}: {
  guidance: CareerGuidance
  sections?: Array<keyof CareerGuidance>
}) {
  if (guidance.status === "unavailable") {
    return <Card><h2 className="font-semibold">Evidence-based guidance</h2><p className="mt-2 text-sm">{guidance.reason || "Guidance was not generated."}</p></Card>
  }
  const blocks: Array<[keyof CareerGuidance, string, string]> = [
    ["career_paths", "Career-path labels", "Grouped from extracted skill categories. Not a job offer."],
    ["skills_to_strengthen", "Skills to strengthen", "Matched from a mention, or mentioned when no job was compared."],
    ["partially_supported", "Partially supported", "Mention-only matches still count in the estimate. Related skills do not."],
    ["project_ideas", "Project ideas", "Taken from the gap practice tasks and mention-only skills."],
    ["short_term", "Near-term roadmap", "Required gaps and their prerequisites, in roadmap order."],
    ["long_term", "Later roadmap", "Preferred gaps, related skills, and employment evidence."],
    ["weekly_focus", "Focus slots", "Order only. Not an estimate of how long a skill takes."],
  ]
  const chosen = sections ? blocks.filter(([key]) => sections.includes(key)) : blocks
  return (
    <div className="space-y-4">
      <Card>
        <h2 className="text-lg font-semibold">Evidence-based guidance</h2>
        <p className="mt-1 text-sm leading-6 text-slate-600 dark:text-slate-300">These notes restate the pipeline. They do not change the readiness estimate.</p>
        {guidance.reason ? <p className="mt-2 text-sm">{guidance.reason}</p> : null}
      </Card>
      {chosen.map(([key, title, note]) => (
        <GuidanceList key={key} title={title} note={note} items={(guidance[key] as GuidanceItem[] | undefined) ?? []} />
      ))}
      {(guidance.github_notes ?? []).length > 0 ? (
        <Card>
          <h3 className="font-semibold">GitHub, separate from the resume</h3>
          <BulletList items={guidance.github_notes} empty="" />
        </Card>
      ) : null}
      {(guidance.limitations ?? []).length > 0 ? (
        <Card>
          <h3 className="font-semibold">Guidance limits</h3>
          <div className="mt-2"><BulletList items={guidance.limitations} empty="" /></div>
        </Card>
      ) : null}
    </div>
  )
}

function GuidanceList({ title, note, items }: { title: string; note: string; items: GuidanceItem[] }) {
  return (
    <Card>
      <h3 className="font-semibold">{title}</h3>
      <p className="mt-1 text-sm text-slate-500">{note}</p>
      {items.length === 0 ? <p className="mt-3 text-sm">None for this analysis.</p> : (
        <ul className="mt-3 space-y-2 text-sm">
          {items.map((item, index) => (
            <li key={`${item.title}-${index}`} className="rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-700">
              <p className="font-medium">{item.title}</p>
              {item.reason ? <p className="mt-1 leading-6">{item.reason}</p> : null}
              {(item.evidence ?? []).length > 0 ? <p className="mt-1 text-slate-500">Evidence: {item.evidence?.join(" · ")}</p> : null}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
