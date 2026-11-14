import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { Navigate } from "react-router-dom"
import { csrfHeaders } from "./api"

export type AuthUser = {
  name: string
  email: string
}

type AuthApi = {
  status: "loading" | "ready"
  user: AuthUser | null
  login: (email: string, password: string) => Promise<void>
  register: (input: {
    name: string
    email: string
    password: string
    confirmPassword: string
  }) => Promise<void>
  logout: () => Promise<void>
  changePassword: (currentPassword: string, password: string, confirmPassword: string) => Promise<string>
  updateName: (name: string) => Promise<void>
}

const AuthContext = createContext<AuthApi | null>(null)

async function send(path: string, payload: unknown) {
  const response = await fetch(path, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...csrfHeaders() },
    body: JSON.stringify(payload),
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const record = body && typeof body === "object" ? (body as { errors?: unknown }) : {}
    const errors = Array.isArray(record.errors) ? record.errors.filter((item): item is string => typeof item === "string") : []
    throw new Error(errors[0] || "The request could not be completed.")
  }
  return body && typeof body === "object" ? (body as Record<string, unknown>) : {}
}

function asUser(value: unknown): AuthUser | null {
  if (!value || typeof value !== "object") return null
  const record = value as { name?: unknown; email?: unknown }
  if (typeof record.name !== "string" || typeof record.email !== "string") return null
  return { name: record.name, email: record.email }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<"loading" | "ready">("loading")
  const [user, setUser] = useState<AuthUser | null>(null)

  useEffect(() => {
    let cancelled = false
    fetch("/api/auth/session", { credentials: "include" })
      .then(async (response) => {
        if (!response.ok) return null
        const body = await response.json().catch(() => null)
        return asUser(body && typeof body === "object" ? (body as { user?: unknown }).user : null)
      })
      .then((next) => {
        if (!cancelled) setUser(next)
      })
      .catch(() => {
        if (!cancelled) setUser(null)
      })
      .finally(() => {
        if (!cancelled) setStatus("ready")
      })
    return () => {
      cancelled = true
    }
  }, [])

  const api = useMemo<AuthApi>(() => ({
    status,
    user,
    async login(email, password) {
      const body = await send("/api/auth/login", { email, password })
      const next = asUser(body.user)
      if (!next) throw new Error("Sign-in could not be completed.")
      setUser(next)
    },
    async register(input) {
      const body = await send("/api/auth/register", {
        name: input.name,
        email: input.email,
        password: input.password,
        confirm_password: input.confirmPassword,
      })
      const next = asUser(body.user)
      if (!next) throw new Error("The account could not be created.")
      setUser(next)
    },
    async logout() {
      await send("/api/auth/logout", {})
      setUser(null)
    },
    async changePassword(currentPassword, password, confirmPassword) {
      const body = await send("/api/auth/change-password", {
        current_password: currentPassword,
        password,
        confirm_password: confirmPassword,
      })
      return typeof body.message === "string" ? body.message : "Your password was updated."
    },
    async updateName(name) {
      const body = await send("/api/auth/profile", { name })
      const next = asUser(body.user)
      if (next) setUser(next)
    },
  }), [status, user])

  return <AuthContext.Provider value={api}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error("useAuth must be used inside AuthProvider")
  return value
}

export function GuestOnly({ children }: { children: ReactNode }) {
  const auth = useAuth()
  if (auth.status === "loading") {
    return <p role="status" className="px-4 py-10 text-sm text-[var(--muted)]">Checking your session…</p>
  }
  if (auth.user) return <Navigate to="/dashboard" replace />
  return children
}
