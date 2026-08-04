import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { usePeriod } from '../state/period'
import { Icon, type IconName } from './icons'

const NAV: { to: string; label: string; end?: boolean; icon: IconName }[] = [
  { to: '/', label: 'Dashboard', end: true, icon: 'dashboard' },
  { to: '/calendar', label: 'Calendar', icon: 'calendarDot' },
  { to: '/timesheet', label: 'Timesheet', icon: 'calendar' },
  { to: '/invoices', label: 'Invoices', icon: 'invoice' },
  { to: '/expenses', label: 'Expenses', icon: 'expenses' },
  { to: '/archive', label: 'Archive', icon: 'archive' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
]

function BrandMark() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-sm font-bold text-white shadow-sm">€</div>
      <div className="leading-tight">
        <div className="text-sm font-semibold text-ink-900">Hyperium</div>
        <div className="text-[11px] text-ink-500">Admin &amp; Finance</div>
      </div>
    </div>
  )
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-0.5">
      {NAV.map((n) => (
        <NavLink
          key={n.to}
          to={n.to}
          end={n.end}
          onClick={onNavigate}
          className={({ isActive }) =>
            `group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              isActive ? 'bg-brand-50 text-brand-700' : 'text-ink-600 hover:bg-slate-100 hover:text-ink-900'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <Icon name={n.icon} className={`h-[18px] w-[18px] ${isActive ? 'text-brand-600' : 'text-ink-400 group-hover:text-ink-600'}`} />
              {n.label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

function PeriodPicker() {
  const { key, setKey, options } = usePeriod()
  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="hidden text-xs font-medium text-ink-500 sm:inline">Period</span>
      <select className="input h-9 w-40 py-0 sm:w-44" value={key} onChange={(e) => setKey(e.target.value)}>
        {options.map((o) => (
          <option key={o.key} value={o.key}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}

export default function Layout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const { pathname } = useLocation()

  // Close the mobile menu on navigation and lock body scroll while it's open.
  useEffect(() => setMenuOpen(false), [pathname])
  useEffect(() => {
    if (!menuOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMenuOpen(false)
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [menuOpen])

  return (
    <div className="flex min-h-full">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-200 bg-white px-3 py-5 md:flex">
        <div className="px-2 pb-7">
          <BrandMark />
        </div>
        <NavItems />
        <div className="mt-auto rounded-lg bg-slate-50 px-3 py-3 text-[11px] leading-relaxed text-ink-500">
          Prepares documents for review. The owner reviews &amp; sends — the app never moves money.
        </div>
      </aside>

      {/* Mobile slide-over menu */}
      {menuOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 animate-fade-in bg-ink-900/40" onClick={() => setMenuOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-64 animate-slide-in-left flex-col bg-white px-3 py-5 shadow-xl">
            <div className="mb-6 flex items-center justify-between px-2">
              <BrandMark />
              <button
                className="grid h-8 w-8 place-items-center rounded-md text-ink-500 hover:bg-slate-100"
                onClick={() => setMenuOpen(false)}
                aria-label="Close menu"
              >
                <Icon name="x" className="h-4 w-4" />
              </button>
            </div>
            <NavItems onNavigate={() => setMenuOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-slate-200 bg-white/85 px-4 py-2.5 backdrop-blur md:px-8">
          <div className="flex items-center gap-2 md:hidden">
            <button
              className="grid h-9 w-9 place-items-center rounded-lg border border-slate-200 text-ink-600 hover:bg-slate-50"
              onClick={() => setMenuOpen(true)}
              aria-label="Open menu"
            >
              <Icon name="menu" className="h-5 w-5" />
            </button>
            <BrandMark />
          </div>
          <div className="ml-auto">
            <PeriodPicker />
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:px-8 md:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
