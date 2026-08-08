import { useState } from 'react'
import type { Comment, DocStatus } from '@af/core'
import { DOC_STATUSES } from '@af/core'
import { api, type DeliverableKind } from '../lib/api'
import { Icon } from './icons'
import { useToast } from './ui'

export const STATUS_META: Record<DocStatus, { label: string; pill: string; dot: string }> = {
  draft: { label: 'Draft', pill: 'bg-slate-100 text-slate-600', dot: 'bg-slate-400' },
  in_progress: { label: 'In progress', pill: 'bg-amber-100 text-amber-700', dot: 'bg-amber-500' },
  ready: { label: 'Ready', pill: 'bg-sky-100 text-sky-700', dot: 'bg-sky-600' },
  final: { label: 'Final', pill: 'bg-emerald-100 text-emerald-700', dot: 'bg-emerald-600' },
}

export function StatusBadge({ status }: { status: DocStatus }) {
  const m = STATUS_META[status]
  return (
    <span className={`pill gap-1.5 ${m.pill}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${m.dot}`} />
      {m.label}
    </span>
  )
}

export function StatusSelect({ status, onChange }: { status: DocStatus; onChange: (s: DocStatus) => void }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`h-2 w-2 shrink-0 rounded-full ${STATUS_META[status].dot}`} />
      <select className="input h-9 w-36 py-0 font-medium" value={status} onChange={(e) => onChange(e.target.value as DocStatus)}>
        {DOC_STATUSES.map((s) => (
          <option key={s} value={s}>
            {STATUS_META[s].label}
          </option>
        ))}
      </select>
    </div>
  )
}

/** Status dropdown + a running to-do / comment list, persisted immediately per document. */
export function DocMeta({
  kind,
  id,
  status,
  comments,
  onChange,
  compact,
}: {
  kind: DeliverableKind
  id: string
  status: DocStatus
  comments: Comment[]
  onChange: (patch: { status: DocStatus; comments: Comment[] }) => void
  compact?: boolean
}) {
  const notify = useToast()
  const [text, setText] = useState('')

  const persist = (next: { status: DocStatus; comments: Comment[] }) => {
    onChange(next)
    api.updateMeta(kind, id, next).catch((e) => notify('err', String(e)))
  }
  const addComment = () => {
    const t = text.trim()
    if (!t) return
    persist({ status, comments: [...comments, { id: crypto.randomUUID(), text: t, done: false, createdAt: new Date().toISOString() }] })
    setText('')
  }
  const open = comments.filter((c) => !c.done).length

  return (
    <div className={compact ? '' : 'card p-5'}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink-900">Status &amp; to-do</h2>
          {open > 0 && <p className="text-xs text-ink-500">{open} open item{open === 1 ? '' : 's'}</p>}
        </div>
        <StatusSelect status={status} onChange={(s) => persist({ status: s, comments })} />
      </div>

      <div className="space-y-0.5">
        {comments.length === 0 && (
          <p className="text-xs text-ink-400">No notes yet — jot down what's still to be done on this document.</p>
        )}
        {comments.map((c) => (
          <div key={c.id} className="group flex items-start gap-2 rounded-md px-1.5 py-1 hover:bg-slate-50">
            <input
              type="checkbox"
              checked={c.done}
              onChange={() => persist({ status, comments: comments.map((x) => (x.id === c.id ? { ...x, done: !x.done } : x)) })}
              className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
            <span className={`flex-1 text-sm ${c.done ? 'text-ink-400 line-through' : 'text-ink-800'}`}>{c.text}</span>
            <button
              onClick={() => persist({ status, comments: comments.filter((x) => x.id !== c.id) })}
              className="text-ink-300 opacity-0 transition-opacity hover:text-rose-500 group-hover:opacity-100"
              title="Remove note"
            >
              <Icon name="x" className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-2">
        <input
          className="input"
          placeholder="Add a note or to-do…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              addComment()
            }
          }}
        />
        <button className="btn-ghost btn-sm shrink-0" onClick={addComment} disabled={!text.trim()}>
          <Icon name="plus" className="h-3.5 w-3.5" /> Add
        </button>
      </div>
    </div>
  )
}
