export type ContactInfo = {
  name?: string | null
  email?: string | null
  phone?: string | null
  location?: string | null
  linkedin?: string | null
  github?: string | null
  leetcode?: string | null
  twitter?: string | null
}

export type SkillEvidence = {
  section?: string
  text?: string
  evidence_type?: string
}

export type DetectedSkill = {
  name: string
  category?: string | null
  evidence_type?: string
  mention_count?: number
  evidence?: SkillEvidence[]
}

export type Section = {
  name: string
  heading?: string | null
  content?: string
}

export type EducationEntry = {
  institution?: string | null
  degree?: string | null
  field_of_study?: string | null
  start_year?: number | null
  end_year?: number | null
  gpa?: string | null
  raw_text?: string
}

export type ExperienceEntry = {
  organization?: string | null
  title?: string | null
  start_date?: string | null
  end_date?: string | null
  description?: string[]
  raw_text?: string
}

export type ProjectEntry = {
  name?: string | null
  description?: string[]
  technologies?: string[]
  links?: string[]
  raw_text?: string
}

export type CertificationEntry = {
  name?: string | null
  issuer?: string | null
  year?: number | null
  kind?: string
  raw_text?: string
}

export type TextProvenance = {
  page_number?: number | null
  method?: string
  char_count?: number
  confidence?: number | null
  suppressed_duplicate?: boolean
}

export type QualityFinding = {
  code?: string
  kind?: string
  severity?: string
  message?: string
}

export type ResumeAnalysis = {
  status: string
  source_format?: string
  file_name?: string | null
  page_count?: number | null
  text_length?: number
  contact?: ContactInfo
  sections?: Section[]
  skills?: DetectedSkill[]
  education?: EducationEntry[]
  experience?: ExperienceEntry[]
  projects?: ProjectEntry[]
  certifications?: CertificationEntry[]
  warnings?: string[]
  errors?: string[]
  text_provenance?: TextProvenance[]
  quality_report?: {
    findings?: QualityFinding[]
    limitations?: string[]
  } | null
}

export type JobRequirement = {
  kind?: string
  priority?: string
  text?: string
  skill_name?: string | null
  certification_name?: string | null
  degree_level?: string | null
  years_min?: number | null
  note?: string | null
}

export type JobAnalysis = {
  status: string
  source_format?: string
  file_name?: string | null
  text_length?: number
  requirements?: JobRequirement[]
  warnings?: string[]
  errors?: string[]
  reason?: string | null
}

export type RequirementMatch = {
  requirement: JobRequirement
  outcome?: string
  evidence_type?: string | null
  evidence?: SkillEvidence[]
  support?: string[]
  related_skills?: string[]
  note?: string | null
  satisfied_by?: string | null
}

export type MatchReport = {
  status?: string
  matches?: RequirementMatch[]
  warnings?: string[]
  matched_count?: number
  related_count?: number
  missing_count?: number
  indeterminate_count?: number
  reason?: string | null
}

export type GitHubSkill = {
  skill_name?: string
  repository?: string
  repository_url?: string
  source_field?: string
  text?: string
  note?: string | null
}

export type GitHubRepository = {
  name?: string
  url?: string
  description?: string | null
  languages?: string[]
  topics?: string[]
  pushed_at?: string | null
  readme_excerpt?: string | null
  warnings?: string[]
}

export type GitHubAnalysis = {
  status: string
  username?: string | null
  profile_url?: string | null
  name?: string | null
  bio?: string | null
  public_repos?: number | null
  repositories?: GitHubRepository[]
  skills?: GitHubSkill[]
  warnings?: string[]
  errors?: string[]
  limitations?: string[]
  reason?: string | null
}

export type Criterion = {
  name?: string
  kind?: string
  priority?: string
  status?: string
  scored?: boolean
  credit?: number
  posting_text?: string
  resume_evidence?: string[]
  detail?: string
}

export type Readiness = {
  status?: string
  job_specific?: boolean
  estimate?: number | null
  band?: string
  summary?: string
  disclaimer?: string
  criteria?: Criterion[]
  github_observations?: string[]
  limitations?: string[]
}

export type Recommendation = {
  skill_name?: string
  priority?: string
  gap_kind?: string
  reason?: string
  posting_text?: string
  prerequisites?: string[]
  practice_task?: string
  evidence_note?: string | null
}

export type RecommendationReport = {
  status?: string
  reason?: string | null
  items?: Recommendation[]
  experience_gaps?: Recommendation[]
  matched_skills?: string[]
  limitations?: string[]
}

export type Milestone = {
  title?: string
  objective?: string
  practice_task?: string
  demonstration?: string
  kind?: string
  skill_name?: string | null
  posting_text?: string | null
  prerequisites?: string[]
  source?: string
}

export type Roadmap = {
  status?: string
  reason?: string | null
  milestones?: Milestone[]
  planning_note?: string | null
  limitations?: string[]
}

export type GuidanceItem = {
  title: string
  kind?: string
  reason?: string
  evidence?: string[]
  priority?: string | null
  source?: string
}

export type CareerGuidance = {
  status?: string
  reason?: string | null
  skills_to_strengthen?: GuidanceItem[]
  partially_supported?: GuidanceItem[]
  project_ideas?: GuidanceItem[]
  career_paths?: GuidanceItem[]
  short_term?: GuidanceItem[]
  long_term?: GuidanceItem[]
  weekly_focus?: GuidanceItem[]
  github_notes?: string[]
  limitations?: string[]
}

export type CareerReport = {
  resume_status?: string
  comparison?: MatchReport | null
  github_status?: string | null
  readiness?: Readiness
  recommendations?: RecommendationReport
  roadmap?: Roadmap
  guidance?: CareerGuidance | null
  limitations?: string[]
}

export type ReportBundle = {
  status: string
  analysis_status?: string
  markdown?: string
  report?: {
    entered_labels?: {
      job_title?: string | null
      company?: string | null
      target_career?: string | null
      note?: string
    }
    career_report?: CareerReport
  }
  skills_csv?: string | null
  comparison_csv?: string | null
  pdf_base64?: string | null
  errors?: string[]
}
