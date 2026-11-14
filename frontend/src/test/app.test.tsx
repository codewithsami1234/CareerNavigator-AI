import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { AppRoutes } from "../App"
import { AuthProvider } from "../auth"
import { MAX_UPLOAD_BYTES, appendBrowserProgress, compareSkillEvidence, fileTooLarge, sliceReport } from "../evidence"
import { WorkspaceProvider } from "../workspace"

let serverWorkspace: unknown = null

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })
}

export function answerKnown(input: RequestInfo | URL, init?: RequestInit): Response | null {
  const url = String(input)
  const method = (init?.method ?? "GET").toUpperCase()
  if (url.includes("/api/auth/session")) {
    return jsonResponse({
      user: { name: "Alex Morgan", email: "alex.morgan@example.com" },
    })
  }
  if (url.includes("/api/me/workspace") && method === "GET") return jsonResponse({ workspace: serverWorkspace })
  if (url.includes("/api/me/workspace")) return jsonResponse({ status: "saved" })
  if (url.includes("/api/health")) return jsonResponse({ status: "ok", service: "CareerNavigator AI" })
  if (url.includes("/api/auth/logout")) return jsonResponse({ status: "signed_out" })
  if (url.includes("/api/auth/sessions")) return jsonResponse({ sessions: [{ current: true, remember: false, created_at: "2026-11-05T12:00:00+00:00" }] })
  return null
}

function renderAt(path: string) {
  return render(
    <AuthProvider>
      <WorkspaceProvider>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
        </MemoryRouter>
      </WorkspaceProvider>
    </AuthProvider>,
  )
}

beforeEach(() => {
  localStorage.clear()
  serverWorkspace = null
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    return answerKnown(input, init) ?? new Response("not found", { status: 404 })
  }))
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("landing and navigation", () => {
  it("shows the product and does not invent a success rate", () => {
    renderAt("/")
    expect(screen.getByRole("heading", { name: /career guidance you can trace/i })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /open workspace/i })).toBeInTheDocument()
    expect(screen.getByText(/layout preview · not a live result/i)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/98%|users hired|accuracy of 9/i)
    expect(document.body.textContent).not.toMatch(/arbiter|hackathon/i)
  })

  it("opens the workspace navigation", async () => {
    const user = userEvent.setup()
    renderAt("/")
    await user.click(screen.getByRole("link", { name: /open workspace/i }))
    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Resume Analyzer" })).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Job Matcher" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Open menu" })).toBeInTheDocument()
  })
})

describe("resume upload", () => {
  it("sends the synthetic sample and renders the skill the API returns", async () => {
    const user = userEvent.setup()
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes("/api/resume")) {
        return new Response(JSON.stringify({
          status: "success",
          file_name: "alex-morgan-synthetic.txt",
          contact: { email: "alex.morgan@example.com", name: null },
          skills: [{
            name: "Python",
            category: "Programming Languages",
            evidence_type: "mentioned",
            mention_count: 1,
            evidence: [{ section: "skills", text: "Python, Java", evidence_type: "mentioned" }],
          }],
          warnings: [],
          errors: [],
          education: [],
          experience: [],
          projects: [],
          certifications: [],
          sections: [],
        }), { status: 200, headers: { "Content-Type": "application/json" } })
      }
      return answerKnown(input, init) ?? new Response("not found", { status: 404 })
    })
    vi.stubGlobal("fetch", fetchMock)
    renderAt("/app/resume")
    await user.click(await screen.findByRole("button", { name: "Use synthetic sample" }))
    expect(screen.getByText(/alex-morgan-synthetic.txt/)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Analyze resume" }))
    expect(await screen.findByText("Python")).toBeInTheDocument()
    expect(screen.getByText("alex.morgan@example.com")).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalled()
  })

  it("asks for a file before analyzing", async () => {
    const user = userEvent.setup()
    renderAt("/app/resume")
    await user.click(await screen.findByRole("button", { name: "Analyze resume" }))
    expect(screen.getByText(/choose a pdf, docx, txt, png, or jpeg resume first/i)).toBeInTheDocument()
  })
})

describe("resume file checks", () => {
  it("rejects an extension the pipeline does not read", async () => {
    renderAt("/resume-analyzer")
    await screen.findByRole("button", { name: "Use synthetic sample" })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const rejected = new File(["nope"], "notes.rtf", { type: "application/rtf" })
    fireEvent.change(input, { target: { files: [rejected] } })
    expect(screen.getByText(/unsupported file type/i)).toBeInTheDocument()
    const fetchMock = vi.mocked(fetch)
    expect(fetchMock.mock.calls.some((call) => String(call[0]).includes("/api/resume"))).toBe(false)
  })

  it("rejects a content type that disagrees with the extension", async () => {
    const user = userEvent.setup()
    renderAt("/resume-analyzer")
    await screen.findByRole("button", { name: "Use synthetic sample" })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    await user.upload(input, new File(["<html>"], "photo.jpg", { type: "text/html" }))
    expect(screen.getByText(/content type does not match/i)).toBeInTheDocument()
  })

  it("shows a progress indicator while the resume request is in flight", async () => {
    const user = userEvent.setup()
    let release: (value: Response) => void = () => {}
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).includes("/api/resume")) {
        return new Promise<Response>((resolve) => {
          release = resolve
        })
      }
      return Promise.resolve(answerKnown(input, init) ?? new Response("not found", { status: 404 }))
    }))
    renderAt("/resume-analyzer")
    await user.click(await screen.findByRole("button", { name: "Use synthetic sample" }))
    await user.click(screen.getByRole("button", { name: "Analyze resume" }))
    expect(await screen.findByRole("progressbar")).toBeInTheDocument()
    release(new Response(JSON.stringify({ status: "success", skills: [], warnings: [], errors: [] }), { status: 200 }))
    expect(await screen.findByText(/reading complete/i)).toBeInTheDocument()
  })
})

describe("job matching", () => {
  it("refuses an empty job description", async () => {
    const user = userEvent.setup()
    renderAt("/app/job")
    const box = await screen.findByRole("textbox", { name: /job description/i })
    await user.clear(box)
    await user.click(screen.getByRole("button", { name: "Read job description" }))
    expect(screen.getByText(/does not fetch job listings/i)).toBeInTheDocument()
  })

  it("restores the description that was read and will not compare a different draft", async () => {
    const user = userEvent.setup()
    serverWorkspace = {
      theme: "light",
      resume: { status: "success", skills: [] },
      job: {
        status: "success",
        requirements: [{ kind: "skill", priority: "required", skill_name: "Python", text: "Python" }],
      },
      jobDraft: "Required qualifications\n- Python",
      analyzedJobText: "Required qualifications\n- Python",
    }
    renderAt("/job-matcher")
    const box = await screen.findByRole("textbox", { name: /job description/i })
    await waitFor(() => expect(box).toHaveValue("Required qualifications\n- Python"))
    expect(screen.getAllByText("Python").length).toBeGreaterThan(0)
    await user.clear(box)
    await user.type(box, "Required qualifications\n- Go")
    await user.click(screen.getByRole("button", { name: "Compare with resume" }))
    expect(screen.getByText(/does not match the description that was read/i)).toBeInTheDocument()
  })
})

describe("routes", () => {
  it("opens the dashboard directly and rejects an unknown address", async () => {
    renderAt("/dashboard")
    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Collapse sidebar" })).toBeInTheDocument()
  })

  it("shows a not-found page instead of inventing a module", () => {
    renderAt("/missing-page")
    expect(screen.getByRole("heading", { name: /not part of the workspace/i })).toBeInTheDocument()
  })
})

describe("evidence helpers", () => {
  it("states the byte count when a file is one byte over the limit", () => {
    const message = fileTooLarge({ size: MAX_UPLOAD_BYTES + 1 } as File)
    expect(message).toContain("too large")
    expect(message).toContain(String(MAX_UPLOAD_BYTES + 1))
    expect(message).toContain(String(MAX_UPLOAD_BYTES))
    expect(message).not.toContain("10.0 MB")
    expect(fileTooLarge({ size: MAX_UPLOAD_BYTES } as File)).toBeNull()
  })

  it("compares names without treating a language mention as proof", () => {
    const result = compareSkillEvidence(["Python", "Kubernetes"], ["python"])
    expect(result.supported).toEqual(["Python"])
    expect(result.resumeOnly).toEqual(["Kubernetes"])
    expect(result.note.toLowerCase()).toContain("not proof of proficiency")
  })

  it("splits a pipeline report without adding a score", () => {
    const slices = sliceReport("# Report\n\n## Resume\nPython\n\n## Job description\nKubernetes\n\n## Skill gaps and suggestions\nGap\n\n## Roadmap\nStep\n\n## GitHub\noctocat\n\n## Report limitations\nNone\n")
    expect(slices.find((item) => item.id === "job")?.markdown).toContain("Kubernetes")
    expect(slices.find((item) => item.id === "job")?.markdown).toContain("does not calculate a second score")
    expect(slices.find((item) => item.id === "github")?.markdown).toContain("octocat")
  })

  it("shows evidence-based guidance stored with the comparison", async () => {
    serverWorkspace = {
      theme: "light",
      resume: { status: "success", file_name: "example.txt", skills: [] },
      career: {
        roadmap: {
          status: "success",
          milestones: [{ title: "SQL", objective: "Be able to use SQL.", kind: "missing_required", source: "suggestion" }],
          limitations: [],
        },
        guidance: {
          status: "success",
          career_paths: [{
            title: "Software engineering",
            kind: "career_path",
            reason: "This label groups those extracted skills. It is not a job offer and it is not a prediction.",
            evidence: ["Python"],
            source: "resume",
          }],
          partially_supported: [{
            title: "React",
            kind: "partial",
            reason: "The supporting lines are not in Experience or Projects, so this is partial support, not demonstrated use.",
            evidence: ["React"],
            source: "resume",
          }],
          skills_to_strengthen: [],
          project_ideas: [],
          short_term: [],
          long_term: [],
          weekly_focus: [],
          github_notes: ["That list is not resume evidence and was not used to choose a career path."],
          limitations: ["Career-path labels are not job offers."],
        },
      },
    }
    renderAt("/career-roadmap")
    expect(await screen.findByRole("heading", { name: "Evidence-based guidance" })).toBeInTheDocument()
    expect(screen.getByText(/not a prediction/i)).toBeInTheDocument()
    expect(screen.getByText(/not resume evidence/i)).toBeInTheDocument()
  })

  it("shows partial support on the skill-gap page", async () => {
    serverWorkspace = {
      theme: "light",
      career: {
        guidance: {
          status: "success",
          partially_supported: [{
            title: "React",
            reason: "this is partial support, not demonstrated use",
          }],
          skills_to_strengthen: [],
          limitations: [],
        },
      },
    }
    renderAt("/skill-gap")
    expect(await screen.findByRole("heading", { name: "Partially supported" })).toBeInTheDocument()
    expect(screen.getByText(/partial support, not demonstrated use/i)).toBeInTheDocument()
  })

  it("labels browser progress as unverified", () => {
    const text = appendBrowserProgress("# Report\n", [{ title: "Practice Kubernetes" }], { "0:Practice Kubernetes": true })
    expect(text).toContain("[x] Practice Kubernetes")
    expect(text).toContain("not verified learning")
  })
})

describe("GitHub errors", () => {
  it("shows rate limiting and network failure without inventing a profile", async () => {
    const user = userEvent.setup()
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const known = answerKnown(input, init)
      if (known) return known
      if (String(input).includes("/api/github")) {
        const body = JSON.parse(String(init?.body ?? "{}")) as { username?: string }
        if (body.username === "limited") {
          return jsonResponse({
            status: "rate_limited",
            username: "limited",
            name: null,
            bio: null,
            repositories: [],
            skills: [],
            errors: ["GitHub rate limit was reached. Wait and try again, or set GITHUB_TOKEN in the environment."],
            reason: "GitHub rate limit was reached. Wait and try again, or set GITHUB_TOKEN in the environment.",
          })
        }
        return jsonResponse({
          status: "failed",
          username: "offline",
          name: null,
          bio: null,
          repositories: [],
          skills: [],
          errors: ["GitHub could not be reached. Check the network connection and try again."],
          reason: "GitHub could not be reached. Check the network connection and try again.",
        })
      }
      return new Response("not found", { status: 404 })
    }))
    renderAt("/github-intelligence")
    const input = await screen.findByLabelText(/username or profile url/i)
    await user.type(input, "limited")
    await user.click(screen.getByRole("button", { name: "Read profile" }))
    expect(await screen.findByRole("alert")).toHaveTextContent(/rate limit was reached/i)
    expect(screen.queryByText(/The Octocat/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Python/i)).not.toBeInTheDocument()
    await user.clear(input)
    await user.type(input, "offline")
    await user.click(screen.getByRole("button", { name: "Read profile" }))
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not be reached/i)
    expect(screen.queryByText(/The Octocat/i)).not.toBeInTheDocument()
  })
})
