import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import type { Settings } from '@af/core'
import { api } from '../lib/api'

interface SettingsCtx {
  settings: Settings | null
  reload: () => void
}

const Ctx = createContext<SettingsCtx | null>(null)

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings | null>(null)
  const reload = () => {
    api.getSettings().then(setSettings).catch(() => setSettings(null))
  }
  useEffect(reload, [])
  return <Ctx.Provider value={{ settings, reload }}>{children}</Ctx.Provider>
}

/** The current settings (null until loaded). */
export function useSettings(): Settings | null {
  return useContext(Ctx)?.settings ?? null
}

export function useSettingsCtx(): SettingsCtx {
  const c = useContext(Ctx)
  if (!c) throw new Error('useSettingsCtx must be used within SettingsProvider')
  return c
}
