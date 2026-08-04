import { useState } from 'react'
import { Icon } from './icons'

/** Compact "duplicate a previous month" control shown above the Timesheet / Expense editors. */
export function CopyFrom({
  noun,
  targetLabel,
  sources,
  onCopy,
}: {
  noun: string
  targetLabel: string
  sources: { key: string; label: string }[]
  onCopy: (key: string) => void
}) {
  const [key, setKey] = useState('')
  if (sources.length === 0) return null
  return (
    <div className="card mb-5 flex flex-wrap items-center gap-3 px-5 py-3">
      <Icon name="copy" className="h-4 w-4 text-ink-400" />
      <span className="text-sm text-ink-600">Start from a previous {noun}:</span>
      <select className="input h-9 w-48 py-0" value={key} onChange={(e) => setKey(e.target.value)}>
        <option value="">Choose a month…</option>
        {sources.map((s) => (
          <option key={s.key} value={s.key}>
            {s.label}
          </option>
        ))}
      </select>
      <button
        className="btn-ghost btn-sm"
        disabled={!key}
        onClick={() => {
          if (key) onCopy(key)
        }}
      >
        Copy into {targetLabel}
      </button>
    </div>
  )
}
