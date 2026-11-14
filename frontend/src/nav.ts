export type AppRoute = {
  to: string
  label: string
  description: string
  icon: string
  end: boolean
}

export const APP_ROUTES: AppRoute[] = [
  {
    to: "/dashboard",
    label: "Dashboard",
    description: "A summary of analyses saved with your account. Empty cards stay empty until you run a step.",
    icon: "grid-1x2",
    end: true,
  },
  {
    to: "/resume-analyzer",
    label: "Resume Analyzer",
    description: "Upload a PDF, DOCX, TXT, PNG, or JPEG resume. The parser returns only what it can read.",
    icon: "file-earmark-text",
    end: false,
  },
  {
    to: "/job-matcher",
    label: "Job Matcher",
    description: "Paste one job description. The readiness number is the pipeline estimate.",
    icon: "briefcase",
    end: false,
  },
  {
    to: "/skill-gap",
    label: "Skill Gap Analysis",
    description: "Matched, missing, and related requirements from the latest comparison.",
    icon: "signpost-split",
    end: false,
  },
  {
    to: "/github-intelligence",
    label: "GitHub Intelligence",
    description: "Read a public GitHub profile. Repository metadata is not proof of proficiency.",
    icon: "github",
    end: false,
  },
  {
    to: "/career-roadmap",
    label: "Career Roadmap",
    description: "Milestones sequenced from the skill gaps. Checkbox progress is local and unverified.",
    icon: "map",
    end: false,
  },
  {
    to: "/reports",
    label: "Reports",
    description: "Preview and download extracts of the pipeline report. No second score is calculated.",
    icon: "file-earmark-bar-graph",
    end: false,
  },
  {
    to: "/settings",
    label: "Settings",
    description: "Your profile, password, and saved analysis.",
    icon: "gear",
    end: false,
  },
]

export function routeFor(pathname: string) {
  return APP_ROUTES.find((item) => (item.end ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`)))
}
