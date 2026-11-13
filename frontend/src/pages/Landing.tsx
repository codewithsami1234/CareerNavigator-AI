import { Link } from "react-router-dom"
import { Logo } from "../components/Logo"
import { useWorkspace } from "../workspace"

const FEATURES = [
  ["file-earmark-text", "Resume intelligence", "Reads PDF, DOCX, TXT, PNG, and JPEG. Scanned pages and photographs use local Tesseract only when you ask for OCR."],
  ["briefcase", "Job matching", "Compares your analyzed resume with a job description you paste. Outcomes are matched, related, missing, or indeterminate."],
  ["signpost-split", "Skill gaps", "Lists missing requirements with the posting text that produced them. Practice tasks are suggestions. No course catalogue is attached."],
  ["github", "GitHub evidence", "Reads a public profile from the GitHub API. A skill is reported only when the taxonomy finds it, and it stays tied to a repository."],
  ["map", "Roadmap", "Sequences the same gaps into milestones. Progress checks are saved with your account and are labeled as unverified."],
  ["file-earmark-bar-graph", "Reports", "Downloads a document built from those results. The readiness number is copied from the pipeline."],
] as const

export function Landing() {
  const { theme, setTheme } = useWorkspace()
  return (
    <div className="min-h-screen text-[var(--text)]">
      <header className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-5">
        <Link to="/" className="flex min-w-0 items-center gap-3">
          <Logo />
          <span className="text-sm font-semibold">CareerNavigator AI</span>
        </Link>
        <div className="flex max-w-full flex-wrap items-center justify-end gap-2">
          <button type="button" className="btn btn-secondary" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            {theme === "dark" ? "Light theme" : "Dark theme"}
          </button>
          <Link to="/sign-in" className="btn btn-secondary">Sign in</Link>
          <Link to="/dashboard" className="btn btn-primary">Open workspace</Link>
        </div>
      </header>
      <main>
        <section className="mx-auto grid max-w-6xl items-center gap-8 px-4 py-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <p className="eyebrow">Evidence you can check</p>
            <h1 className="mt-3 max-w-xl text-4xl font-semibold leading-tight sm:text-5xl">
              Career guidance you can trace to the evidence.
            </h1>
            <p className="muted mt-4 max-w-xl text-lg leading-8">
              CareerNavigator AI connects a resume, a job description you supply, the gaps between them, and public GitHub metadata. Every score is a rule-based estimate with its inputs on screen.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link to="/resume-analyzer" className="btn btn-primary">
                Analyze a resume <i className="bi bi-arrow-right" aria-hidden="true" />
              </Link>
              <a href="#how-it-works" className="btn btn-secondary">How it works</a>
            </div>
          </div>
          <div className="hero-panel" aria-label="Workspace layout preview">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--muted)]">Layout preview · not a live result</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {[
                ["Resume", "Skills, contact, and provenance after a file is read"],
                ["Job match", "Matched, missing, and the readiness denominator"],
                ["GitHub", "Public metadata, or an honest error"],
                ["Roadmap", "Milestones from the gaps, with your own progress ticks"],
              ].map(([label, copy]) => (
                <div key={label} className="rounded-2xl bg-white/75 p-4">
                  <p className="text-sm font-semibold">{label}</p>
                  <p className="muted mt-1 text-sm">{copy}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
        <section className="mx-auto max-w-6xl px-4 py-8">
          <h2 className="text-2xl font-semibold">What the workspace actually does</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {FEATURES.map(([icon, title, body]) => (
              <article key={title} className="surface p-5">
                <span className="icon-well"><i className={`bi bi-${icon}`} aria-hidden="true" /></span>
                <h3 className="mt-3 font-semibold">{title}</h3>
                <p className="muted mt-2 text-sm leading-6">{body}</p>
              </article>
            ))}
          </div>
        </section>
        <section id="how-it-works" className="mx-auto max-w-6xl px-4 py-8">
          <h2 className="text-2xl font-semibold">How it works</h2>
          <ol className="mt-6 grid gap-4 md:grid-cols-4">
            {[
              ["1", "Upload a resume", "PDF, DOCX, TXT, PNG, or JPEG. OCR is optional and local."],
              ["2", "Paste one job", "There is no job board. The text you provide is the posting."],
              ["3", "Read the evidence", "Matched skills, missing skills, and GitHub observations stay labeled."],
              ["4", "Export the report", "The download is the same analysis, not a new narrative."],
            ].map(([step, title, body]) => (
              <li key={step} className="surface p-5">
                <p className="text-sm font-semibold text-[#8a5a24]">{step}</p>
                <h3 className="mt-2 font-semibold">{title}</h3>
                <p className="muted mt-2 text-sm leading-6">{body}</p>
              </li>
            ))}
          </ol>
        </section>
        <section className="mx-auto grid max-w-6xl gap-4 px-4 pb-16 md:grid-cols-3">
          {[
            ["cpu", "Rule-based", "The resume engine is not described as a trained model."],
            ["github", "Public GitHub only", "No GitHub password is requested. A failure leaves the resume intact."],
            ["shield-check", "Your account", "Saved analysis stays with the signed-in account until you delete it. Resume files are not kept."],
          ].map(([icon, title, body]) => (
            <div key={title} className="surface flex gap-3 p-5">
              <span className="icon-well"><i className={`bi bi-${icon}`} aria-hidden="true" /></span>
              <div>
                <h3 className="font-semibold">{title}</h3>
                <p className="muted mt-1 text-sm leading-6">{body}</p>
              </div>
            </div>
          ))}
        </section>
      </main>
      <footer className="border-t border-[var(--line)] px-4 py-8 text-sm text-[var(--muted)]">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p>CareerNavigator AI</p>
          <p>Runs locally. Not a hosted hiring product.</p>
        </div>
      </footer>
    </div>
  )
}
