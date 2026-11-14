import type { DetectedSkill, Milestone } from "./types"

export function uniqueNames(values: string[]) {
  const seen = new Set<string>()
  const names: string[] = []
  for (const value of values) {
    const trimmed = value.trim()
    const key = trimmed.toLowerCase()
    if (!trimmed || seen.has(key)) continue
    seen.add(key)
    names.push(trimmed)
  }
  return names
}

export function groupSkills(skills: DetectedSkill[]) {
  const groups = new Map<string, DetectedSkill[]>()
  for (const skill of skills) {
    const category = skill.category?.trim() || "Uncategorised"
    const list = groups.get(category) ?? []
    list.push(skill)
    groups.set(category, list)
  }
  return [...groups.entries()]
}

export const EVIDENCE_NOTE =
  "A shared name means that taxonomy label appears in both results. It is not proof of proficiency. A resume skill missing from GitHub was not seen in the scanned public metadata, which is not proof that the skill is absent."

export function compareSkillEvidence(resumeNames: string[], githubNames: string[]) {
  const resume = uniqueNames(resumeNames)
  const github = uniqueNames(githubNames)
  const githubKeys = new Set(github.map((name) => name.toLowerCase()))
  const resumeKeys = new Set(resume.map((name) => name.toLowerCase()))
  return {
    supported: resume.filter((name) => githubKeys.has(name.toLowerCase())),
    resumeOnly: resume.filter((name) => !githubKeys.has(name.toLowerCase())),
    githubOnly: github.filter((name) => !resumeKeys.has(name.toLowerCase())),
    note: EVIDENCE_NOTE,
  }
}

export function progressKey(index: number, title: string) {
  return `${index}:${title}`
}

export function appendBrowserProgress(
  markdown: string,
  milestones: Milestone[],
  progress: Record<string, boolean>,
) {
  const lines = [
    "",
    "## Progress marked in this browser",
    "These checks were ticked on this device. They are not verified learning.",
    "",
  ]
  if (milestones.length === 0) {
    lines.push("No roadmap milestones were available to mark.")
  }
  milestones.forEach((item, index) => {
    const title = item.title || "Milestone"
    const mark = progress[progressKey(index, title)] ? "x" : " "
    lines.push(`- [${mark}] ${title}`)
  })
  return `${markdown.replace(/\s*$/, "")}\n${lines.join("\n")}\n`
}

export type ReportSlice = {
  id: string
  title: string
  markdown: string
}

const REPORT_SLICES: { id: string; title: string; start: string; end: string }[] = [
  { id: "resume", title: "Resume analysis", start: "## Resume", end: "## Job description" },
  { id: "job", title: "Job match", start: "## Job description", end: "## Skill gaps" },
  { id: "gaps", title: "Skill gap", start: "## Skill gaps", end: "## Roadmap" },
  { id: "roadmap", title: "Career roadmap", start: "## Roadmap", end: "## Evidence-based guidance" },
  { id: "guidance", title: "Evidence-based guidance", start: "## Evidence-based guidance", end: "## GitHub" },
  { id: "github", title: "GitHub analysis", start: "## GitHub", end: "## Report limitations" },
]

function between(markdown: string, start: string, end: string) {
  const from = markdown.indexOf(start)
  if (from < 0) return ""
  const to = markdown.indexOf(end, from + start.length)
  return (to < 0 ? markdown.slice(from) : markdown.slice(from, to)).trim()
}

export function sliceReport(markdown: string): ReportSlice[] {
  const note = "Extracted from the pipeline report. This file does not calculate a second score.\n\n"
  return REPORT_SLICES.map((item) => {
    const body = between(markdown, item.start, item.end)
    return { id: item.id, title: item.title, markdown: body ? note + body + "\n" : "" }
  })
}

export function downloadText(filename: string, content: string, type: string) {
  downloadBlob(filename, new Blob([content], { type }))
}

export function downloadBase64(filename: string, encoded: string, type: string) {
  const binary = atob(encoded)
  const bytes = new Uint8Array(binary.length)
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index)
  downloadBlob(filename, new Blob([bytes], { type }))
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024

export function fileTooLarge(file: File) {
  if (file.size <= MAX_UPLOAD_BYTES) return null
  return `File is too large (${file.size} bytes). The limit is ${MAX_UPLOAD_BYTES} bytes (10 MB).`
}
