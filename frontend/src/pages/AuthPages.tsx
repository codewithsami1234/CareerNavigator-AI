import { useState, type FormEvent, type ReactNode } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { useAuth } from "../auth"
import { Logo } from "../components/Logo"
import { Alert, Button, Field, inputClass } from "../components/ui"

function safeNext(value: string | null) {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return "/dashboard"
  if (value.startsWith("/sign-in") || value.startsWith("/sign-up")) return "/dashboard"
  return value
}

function AuthFrame({ title, lede, children }: { title: string; lede: string; children: ReactNode }) {
  return (
    <main className="min-h-screen px-4 py-10 text-[var(--text)]">
      <div className="mx-auto w-full max-w-md">
        <Link to="/" className="mb-6 flex items-center gap-3">
          <Logo />
          <span className="text-sm font-semibold">CareerNavigator AI</span>
        </Link>
        <section className="surface w-full p-6 sm:p-8">
          <h1 className="text-2xl font-semibold">{title}</h1>
          <p className="muted mt-2 text-sm leading-6">{lede}</p>
          <div className="mt-6">{children}</div>
        </section>
      </div>
    </main>
  )
}

function passwordProblem(password: string) {
  if (password.length < 8) return "Use at least 8 characters."
  return ""
}

export function SignInPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!email.trim() || !password) {
      setError("Enter your email and password.")
      return
    }
    setBusy(true)
    setError("")
    try {
      await auth.login(email.trim(), password)
      navigate(safeNext(params.get("next")))
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign-in could not be completed.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthFrame title="Sign in" lede="Use the email and password for your account.">
      <form className="grid w-full gap-4" onSubmit={onSubmit}>
        {error ? <Alert tone="error">{error}</Alert> : null}
        <Field label="Email">
          <input className={inputClass} type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} />
        </Field>
        <Field label="Password">
          <input className={inputClass} type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </Field>
        <Button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</Button>
        <p className="text-sm">New here? <Link className="link-accent" to="/sign-up">Create an account</Link></p>
      </form>
    </AuthFrame>
  )
}

export function SignUpPage() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    if (!name.trim()) return setError("Enter your name.")
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) return setError("Enter a valid email address.")
    const weak = passwordProblem(password)
    if (weak) return setError(weak)
    if (password !== confirm) return setError("The passwords do not match.")
    setBusy(true)
    setError("")
    try {
      await auth.register({ name: name.trim(), email: email.trim(), password, confirmPassword: confirm })
      navigate("/dashboard")
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The account could not be created.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthFrame title="Create an account" lede="Your resume analysis stays with this account.">
      <form className="grid w-full gap-4" onSubmit={onSubmit}>
        {error ? <Alert tone="error">{error}</Alert> : null}
        <Field label="Full name">
          <input className={inputClass} autoComplete="name" value={name} onChange={(event) => setName(event.target.value)} />
        </Field>
        <Field label="Email">
          <input className={inputClass} type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} />
        </Field>
        <Field label="Password">
          <input className={inputClass} type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </Field>
        <Field label="Confirm password">
          <input className={inputClass} type="password" autoComplete="new-password" value={confirm} onChange={(event) => setConfirm(event.target.value)} />
        </Field>
        <Button type="submit" disabled={busy}>{busy ? "Creating account…" : "Create account"}</Button>
        <p className="text-sm">Already have an account? <Link className="link-accent" to="/sign-in">Sign in</Link></p>
      </form>
    </AuthFrame>
  )
}

export function TermsPage() {
  return (
    <AuthFrame title="Terms" lede="CareerNavigator AI reads the resume and job text you provide and shows a rule-based estimate.">
      <div className="space-y-3 text-sm leading-6">
        <p>The estimate is not a hiring decision, an ATS score, or a promise of a job.</p>
        <p>You are responsible for the documents you upload. Do not upload someone else’s resume without permission.</p>
        <p>The service can refuse a file it cannot read. Uploaded files are not kept after the analysis finishes.</p>
      </div>
    </AuthFrame>
  )
}

export function PrivacyPage() {
  return (
    <AuthFrame title="Privacy" lede="Your account and your analysis stay separate from other people’s accounts.">
      <div className="space-y-3 text-sm leading-6">
        <p>Your password is stored in a protected form. The sign-in cookie stays on this server’s session and is not put in browser storage.</p>
        <p>Saved analysis, including text extracted from a resume, is stored for your account until you delete it. Resume files themselves are not kept.</p>
      </div>
    </AuthFrame>
  )
}

export function AccountPanel() {
  const auth = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState(auth.user?.name ?? "")
  const [current, setCurrent] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")

  return (
    <div className="space-y-4">
      <section className="surface p-5">
        <h2 className="text-lg font-semibold">Profile</h2>
        <p className="muted mt-1 text-sm">{auth.user?.email}</p>
        <form
          className="mt-4 grid max-w-md gap-3"
          onSubmit={async (event) => {
            event.preventDefault()
            setError("")
            try {
              await auth.updateName(name)
              setMessage("Your name was updated.")
            } catch (reason) {
              setError(reason instanceof Error ? reason.message : "The name could not be updated.")
            }
          }}
        >
          <Field label="Full name">
            <input className={inputClass} value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
          <Button type="submit" variant="secondary">Save name</Button>
        </form>
      </section>
      <section className="surface p-5">
        <h2 className="text-lg font-semibold">Password</h2>
        <form
          className="mt-4 grid max-w-md gap-3"
          onSubmit={async (event) => {
            event.preventDefault()
            const weak = passwordProblem(password)
            if (weak) return setError(weak)
            if (password !== confirm) return setError("The passwords do not match.")
            setError("")
            try {
              setMessage(await auth.changePassword(current, password, confirm))
              setCurrent("")
              setPassword("")
              setConfirm("")
            } catch (reason) {
              setError(reason instanceof Error ? reason.message : "The password could not be updated.")
            }
          }}
        >
          <Field label="Current password">
            <input className={inputClass} type="password" autoComplete="current-password" value={current} onChange={(event) => setCurrent(event.target.value)} />
          </Field>
          <Field label="New password">
            <input className={inputClass} type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </Field>
          <Field label="Confirm new password">
            <input className={inputClass} type="password" autoComplete="new-password" value={confirm} onChange={(event) => setConfirm(event.target.value)} />
          </Field>
          <Button type="submit" variant="secondary">Change password</Button>
        </form>
      </section>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}
      <Button
        variant="secondary"
        onClick={() => {
          navigate("/")
          void auth.logout()
        }}
      >
        Sign out
      </Button>
    </div>
  )
}
