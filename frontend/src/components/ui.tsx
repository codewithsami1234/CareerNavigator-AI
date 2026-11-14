import { createContext, useContext, useEffect, useState, type ButtonHTMLAttributes, type HTMLAttributes, type ReactNode } from "react"

const buttonStyles = {
  primary: "btn btn-primary",
  secondary: "btn btn-secondary",
  ghost: "btn btn-ghost",
  danger: "btn btn-danger",
}

export function Button({
  variant = "primary",
  className = "",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: keyof typeof buttonStyles }) {
  return <button type={type} className={`${buttonStyles[variant]} ${className}`} {...props} />
}

export function GradientButton(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <Button variant="primary" {...props} />
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`surface surface-hover p-5 ${className}`}>{children}</section>
}

export function PremiumCard({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`premium-card surface-hover p-5 ${className}`}>{children}</section>
}

export function GradientHero({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`hero-panel ${className}`}>{children}</section>
}

export function GoldButton(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <Button variant="primary" {...props} />
}

export function GlassCard({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`glass-card surface-hover p-5 ${className}`}>{children}</section>
}

export function SectionHeader({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow?: string
  title: string
  subtitle?: string
}) {
  return (
    <header>
      {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
      <h2 className={`text-xl font-semibold ${eyebrow ? "mt-2" : ""}`}>{title}</h2>
      {subtitle ? <p className="muted mt-1 max-w-2xl text-sm leading-6">{subtitle}</p> : null}
    </header>
  )
}

export function PageHeader({
  title,
  subtitle,
}: {
  title: string
  subtitle?: string
}) {
  return (
    <div className="min-w-0">
      <h1 className="truncate text-xl font-semibold sm:text-2xl">{title}</h1>
      {subtitle ? <p className="muted mt-1 text-sm leading-6">{subtitle}</p> : null}
    </div>
  )
}

export function StatCard({
  label,
  value,
  detail,
  icon,
}: {
  label: string
  value: string
  detail: string
  icon?: string
}) {
  return (
    <Card className="stat-card gradient-border">
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[var(--muted)]">{label}</p>
        {icon ? <i className={`bi bi-${icon} icon-gold`} aria-hidden="true" /> : null}
      </div>
      <p className="stat-value">{value}</p>
      <p className="muted mt-1 text-sm">{detail}</p>
    </Card>
  )
}

export function Alert({
  tone = "info",
  children,
}: {
  tone?: "info" | "success" | "warning" | "error"
  children: ReactNode
}) {
  return <div role="alert" className={`alert alert-${tone}`}>{children}</div>
}

export function EmptyState({
  title,
  body,
  action,
  icon = "stars",
}: {
  title: string
  body: string
  action?: ReactNode
  icon?: string
}) {
  return (
    <Card className="border-dashed text-center">
      <div className="icon-well mx-auto mb-3 h-12 w-12 rounded-2xl">
        <i className={`bi bi-${icon} text-xl`} aria-hidden="true" />
      </div>
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="muted mx-auto mt-2 max-w-2xl text-sm leading-6">{body}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </Card>
  )
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <label className="field-label">
      {label}
      {hint ? <span className="field-hint">{hint}</span> : null}
      <div className="mt-2">{children}</div>
    </label>
  )
}

export const inputClass = "field-control"

export function StatusBadge({ status }: { status?: string | null }) {
  const value = status || "unknown"
  const tone =
    value === "success"
      ? "badge-ok"
      : value === "partial" || value === "needs_ocr" || value === "rate_limited"
        ? "badge-warn"
        : value === "failed" || value === "empty"
          ? "badge-bad"
          : "badge-neutral"
  return <span className={`badge ${tone}`}>{value}</span>
}

export function Skeleton() {
  return <LoadingSkeleton />
}

export function LoadingSkeleton() {
  return (
    <div aria-hidden="true" className="space-y-3">
      <div className="skeleton h-4 w-40" />
      <div className="skeleton h-24" />
      <div className="skeleton h-24" />
    </div>
  )
}

export function UploadZone({
  active = false,
  children,
  className = "",
  ...props
}: {
  active?: boolean
  children: ReactNode
} & HTMLAttributes<HTMLDivElement>) {
  return <div className={`upload-zone ${active ? "is-over" : ""} ${className}`} {...props}>{children}</div>
}

export function ProgressIndicator({ label }: { label: string }) {
  return (
    <div aria-live="polite">
      <p className="mb-2 text-sm">{label}</p>
      <div className="progress-track" role="progressbar" aria-valuetext={label}>
        <div className="progress-bar" />
      </div>
    </div>
  )
}

export function SkillBadge({ children }: { children: ReactNode }) {
  return <span className="skill-badge">{children}</span>
}

export function ProgressRing({ value, label }: { value: number; label: string }) {
  const amount = Math.max(0, Math.min(100, value))
  const radius = 28
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (amount / 100) * circumference
  return (
    <div className="progress-ring" role="img" aria-label={`${label}: ${amount} out of 100`}>
      <svg viewBox="0 0 72 72" width="84" height="84" aria-hidden="true">
        <circle className="ring-track" cx="36" cy="36" r={radius} />
        <circle className="ring-value" cx="36" cy="36" r={radius} strokeDasharray={circumference} strokeDashoffset={offset} />
      </svg>
      <span>{amount}</span>
    </div>
  )
}

export function BulletList({ items, empty }: { items?: string[]; empty: string }) {
  const rows = (items ?? []).filter(Boolean)
  if (rows.length === 0) {
    if (!empty) return null
    return <p className="muted text-sm">{empty}</p>
  }
  return (
    <ul className="space-y-2 text-sm leading-6">
      {rows.map((item) => (
        <li key={item} className="warm-row px-3 py-2">{item}</li>
      ))}
    </ul>
  )
}

type ToastApi = { push: (text: string) => void }
const ToastContext = createContext<ToastApi>({ push: () => {} })

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<{ id: number; text: string }[]>([])

  function push(text: string) {
    const id = Date.now() + Math.random()
    setItems((current) => [...current, { id, text }].slice(-3))
  }

  useEffect(() => {
    if (items.length === 0) return
    const timer = window.setTimeout(() => setItems((current) => current.slice(1)), 2800)
    return () => window.clearTimeout(timer)
  }, [items])

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div className="toast-stack" aria-live="polite">
        {items.map((item) => <div key={item.id} className="toast" role="status">{item.text}</div>)}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}
