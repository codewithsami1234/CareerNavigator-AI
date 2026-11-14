import { Link } from "react-router-dom"

export function NotFound() {
  return (
    <div className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-16 text-[var(--text)]">
      <p className="eyebrow">404</p>
      <h1 className="mt-3 text-3xl font-semibold">This page is not part of the workspace.</h1>
      <p className="muted mt-3 text-sm leading-6">
        The address does not match a CareerNavigator page. Nothing was analyzed.
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Link to="/dashboard" className="btn btn-primary">Open overview</Link>
        <Link to="/" className="btn btn-secondary">Back to the landing page</Link>
      </div>
    </div>
  )
}
