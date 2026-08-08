import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import { currentPeriod, monthLabel, parsePeriodKey, periodKey } from '@af/core'

interface PeriodCtx {
  key: string
  label: string
  setKey: (k: string) => void
  options: { key: string; label: string }[]
}

const Ctx = createContext<PeriodCtx | null>(null)

function recentKeys(count: number): { key: string; label: string }[] {
  const now = currentPeriod(new Date())
  const out: { key: string; label: string }[] = []
  let y = now.year
  let m = now.month
  for (let i = 0; i < count; i++) {
    const p = { year: y, month: m }
    out.push({ key: periodKey(p), label: monthLabel(p) })
    m -= 1
    if (m === 0) {
      m = 12
      y -= 1
    }
  }
  return out
}

export function PeriodProvider({ children }: { children: ReactNode }) {
  const [key, setKey] = useState<string>(() => localStorage.getItem('af.period') ?? periodKey(currentPeriod(new Date())))
  const value = useMemo<PeriodCtx>(
    () => ({
      key,
      label: monthLabel(parsePeriodKey(key)),
      setKey: (k) => {
        localStorage.setItem('af.period', k)
        setKey(k)
      },
      options: recentKeys(18),
    }),
    [key],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function usePeriod(): PeriodCtx {
  const c = useContext(Ctx)
  if (!c) throw new Error('usePeriod must be used within PeriodProvider')
  return c
}
