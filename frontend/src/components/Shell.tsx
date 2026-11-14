import { Suspense, useEffect, useRef, useState, type CSSProperties } from "react"
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom"
import { useAuth } from "../auth"
import { Logo } from "./Logo"
import { APP_ROUTES, routeFor } from "../nav"
import { useWorkspace } from "../workspace"
import { PageHeader, useToast } from "./ui"

const SIDEBAR_KEY = "careernavigator.sidebar"

function Brand({ compact = false, onNavigate }: { compact?: boolean; onNavigate?: () => void }) {
  return (
    <NavLink to="/dashboard" end onClick={onNavigate} className={`flex min-w-0 items-center gap-3 ${compact ? "justify-center" : ""}`}>
      <Logo size={compact ? 32 : 36} />
      {compact ? <span className="sr-only">CareerNavigator AI</span> : (
        <span className="min-w-0">
          <span className="block truncate text-sm font-semibold">CareerNavigator AI</span>
        </span>
      )}
    </NavLink>
  )
}

function SideLinks({ compact, onNavigate }: { compact: boolean; onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1" aria-label="Workspace">
      {APP_ROUTES.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          title={item.label}
          aria-label={item.label}
          onClick={onNavigate}
          className={({ isActive }) => `nav-link ${isActive ? "active" : ""} ${compact ? "justify-center px-2" : ""}`}
        >
          <i className={`bi bi-${item.icon} text-base`} aria-hidden="true" />
          <span className={compact ? "sr-only" : "truncate"}>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase() ?? "").join("") || "CN"
}

function AccountFooter({ compact, onSignOut }: { compact: boolean; onSignOut: () => void }) {
  const auth = useAuth()
  const name = auth.user?.name || "Account"
  return (
    <div className={`sidebar-foot ${compact ? "is-compact" : ""}`}>
      <div className="account-chip" title={auth.user?.email || "Signed in"}>
        <span className="account-mark" aria-hidden="true">{initials(name)}</span>
        {compact ? <span className="sr-only">{name}</span> : (
          <span className="min-w-0">
            <span className="block truncate text-xs font-semibold leading-4">{name}</span>
            <span className="muted block truncate text-[11px] leading-4">Signed in</span>
          </span>
        )}
      </div>
      <button type="button" className="btn btn-secondary sidebar-signout" onClick={onSignOut}>
        <i className="bi bi-box-arrow-right" aria-hidden="true" />
        {compact ? <span className="sr-only">Sign out</span> : "Sign out"}
      </button>
    </div>
  )
}

export function Shell() {
  const { theme, setTheme } = useWorkspace()
  const auth = useAuth()
  const navigate = useNavigate()
  const { push } = useToast()
  const { pathname } = useLocation()
  const current = routeFor(pathname)
  const [open, setOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(SIDEBAR_KEY) === "collapsed")
  const menuRef = useRef<HTMLButtonElement>(null)
  const drawerRef = useRef<HTMLElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    localStorage.setItem(SIDEBAR_KEY, collapsed ? "collapsed" : "expanded")
  }, [collapsed])

  useEffect(() => {
    setOpen(false)
  }, [pathname])

  useEffect(() => {
    if (!open) return
    const drawer = drawerRef.current
    const previous = document.body.style.overflow
    document.body.style.overflow = "hidden"
    const focusable = () => [...(drawer?.querySelectorAll<HTMLElement>("a, button, input, select, textarea") ?? [])].filter((el) => !el.hasAttribute("disabled"))
    closeRef.current?.focus()
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false)
        menuRef.current?.focus()
        return
      }
      if (event.key !== "Tab") return
      const items = focusable()
      if (items.length === 0) return
      const first = items[0]
      const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    window.addEventListener("keydown", onKey)
    return () => {
      document.body.style.overflow = previous
      window.removeEventListener("keydown", onKey)
    }
  }, [open])

  function signOut() {
    navigate("/")
    void auth.logout()
  }

  function closeDrawer() {
    setOpen(false)
    menuRef.current?.focus()
  }

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark"
    setTheme(next)
    push(next === "dark" ? "Dark theme saved in this browser." : "Light theme saved in this browser.")
  }

  const sidebarWidth = collapsed ? "4.75rem" : "17.5rem"

  return (
    <div className={`app-frame text-[var(--text)] ${open ? "is-drawer-open" : ""}`} style={{ "--sidebar-width": sidebarWidth } as CSSProperties}>
      <a href="#workspace-main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-xl focus:bg-[var(--surface)] focus:px-3 focus:py-2">
        Skip to content
      </a>
      <aside className="app-sidebar" aria-label="Workspace sidebar">
        <div className={`flex gap-2 px-3 py-4 ${collapsed ? "flex-col items-center" : "items-center justify-between"}`}>
          <Brand compact={collapsed} />
          <button
            type="button"
            className="icon-btn"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={() => setCollapsed((value) => !value)}
          >
            <i className={`bi ${collapsed ? "bi-layout-sidebar-inset" : "bi-layout-sidebar"}`} aria-hidden="true" />
          </button>
        </div>
        <div className="app-sidebar-scroll">
          <SideLinks compact={collapsed} />
        </div>
        <AccountFooter compact={collapsed} onSignOut={signOut} />
      </aside>

      {open ? (
        <div className="drawer-layer">
          <button type="button" className="absolute inset-0 bg-[rgba(41,37,31,0.45)]" aria-label="Close menu" onClick={closeDrawer} />
          <aside ref={drawerRef} className="drawer-panel" role="dialog" aria-modal="true" aria-label="Workspace menu">
            <div className="mb-4 flex items-center justify-between">
              <Brand onNavigate={() => setOpen(false)} />
              <button ref={closeRef} type="button" aria-label="Close menu" className="icon-btn" onClick={closeDrawer}>
                <i className="bi bi-x-lg" aria-hidden="true" />
              </button>
            </div>
            <div className="app-sidebar-scroll">
              <SideLinks compact={false} onNavigate={() => setOpen(false)} />
            </div>
            <AccountFooter compact={false} onSignOut={signOut} />
          </aside>
        </div>
      ) : null}

      <div className="app-main">
        <header className="app-topbar">
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <button ref={menuRef} type="button" className="icon-btn menu-toggle" aria-label="Open menu" aria-expanded={open} onClick={() => setOpen(true)}>
                <i className="bi bi-list" aria-hidden="true" />
              </button>
              <PageHeader title={current?.label ?? "Page not found"} />
            </div>
            <button
              type="button"
              className="icon-btn"
              aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              onClick={toggleTheme}
            >
              <i className={`bi ${theme === "dark" ? "bi-sun" : "bi-moon-stars"}`} aria-hidden="true" />
            </button>
          </div>
        </header>
        <main id="workspace-main" className="page-enter mx-auto w-full max-w-6xl break-words px-4 py-5">
          <Suspense fallback={<p className="muted text-sm" role="status">Loading this page…</p>}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}
