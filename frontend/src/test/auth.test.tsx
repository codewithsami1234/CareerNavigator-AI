import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { afterEach, describe, expect, it, vi } from "vitest"
import { AppRoutes } from "../App"
import { AuthProvider } from "../auth"
import { WorkspaceProvider } from "../workspace"

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })
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

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("authentication screens", () => {
  it("shows registration errors before calling the server", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).includes("/api/auth/session")) return json({ user: null }, 401)
      return json({ status: "accepted", message: "unused" })
    })
    vi.stubGlobal("fetch", fetchMock)
    const user = userEvent.setup()
    renderAt("/sign-up")
    await user.click(await screen.findByRole("button", { name: "Create account" }))
    expect(screen.getByText(/enter your name/i)).toBeInTheDocument()
    await user.type(screen.getByLabelText(/full name/i), "Ada Lovelace")
    await user.type(screen.getByLabelText(/^email$/i), "ada@example.com")
    await user.type(screen.getByLabelText(/^password$/i), "short1")
    await user.type(screen.getByLabelText(/confirm password/i), "short1")
    await user.click(screen.getByRole("button", { name: "Create account" }))
    expect(screen.getByText(/at least 8/i)).toBeInTheDocument()
    await user.clear(screen.getByLabelText(/^password$/i))
    await user.clear(screen.getByLabelText(/confirm password/i))
    await user.type(screen.getByLabelText(/^password$/i), "Correct-Horse-12")
    await user.type(screen.getByLabelText(/confirm password/i), "Correct-Horse-13")
    await user.click(screen.getByRole("button", { name: "Create account" }))
    expect(screen.getByText(/do not match/i)).toBeInTheDocument()
    expect(fetchMock.mock.calls.some((call) => String(call[0]).includes("/api/auth/register"))).toBe(false)
  })

  it("shows a sign-in error from the server", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes("/api/auth/session")) return json({ user: null }, 401)
      if (url.includes("/api/auth/login")) return json({ errors: ["The email or password is not correct."] }, 401)
      return json({ status: "ok" })
    }))
    const user = userEvent.setup()
    renderAt("/sign-in")
    await user.type(await screen.findByLabelText(/^email$/i), "ada@example.com")
    await user.type(screen.getByLabelText(/^password$/i), "Correct-Horse-12")
    await user.click(screen.getByRole("button", { name: "Sign in" }))
    expect(await screen.findByRole("alert")).toHaveTextContent(/email or password is not correct/i)
  })

  it("sends visitors without a session to sign in", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ user: null }, 401)))
    renderAt("/dashboard")
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Analyze resume" })).not.toBeInTheDocument()
  })

  it("keeps the session check on screen while it is loading", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})))
    renderAt("/resume-analyzer")
    expect(screen.getByRole("status")).toHaveTextContent(/checking your session/i)
  })

  it("signs out and returns to the welcome page", async () => {
    let signedIn = true
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = (init?.method ?? "GET").toUpperCase()
      if (url.includes("/api/auth/logout")) {
        signedIn = false
        return json({ status: "signed_out" })
      }
      if (url.includes("/api/auth/session")) {
        return signedIn
          ? json({ user: { name: "Ada Lovelace", email: "ada@example.com" } })
          : json({ user: null }, 401)
      }
      if (url.includes("/api/me/workspace") && method === "GET") return json({ workspace: null })
      if (url.includes("/api/health")) return json({ status: "ok", service: "CareerNavigator AI" })
      return json({ status: "ok" })
    }))
    const user = userEvent.setup()
    renderAt("/dashboard")
    expect(await screen.findByText(/welcome back, ada/i)).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: "Sign out" }))
    expect(await screen.findByRole("heading", { name: /career guidance you can trace/i })).toBeInTheDocument()
  })

  it("uses a form that can shrink on a narrow screen", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ user: null }, 401)))
    renderAt("/sign-in")
    const form = (await screen.findByRole("button", { name: "Sign in" })).closest("form")
    expect(form?.className).toContain("w-full")
    expect(document.querySelector(".max-w-md")).not.toBeNull()
    expect(screen.getByLabelText(/^email$/i).className).toContain("field-control")
  })
})
