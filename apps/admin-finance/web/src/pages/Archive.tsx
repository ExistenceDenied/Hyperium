import { useEffect, useMemo, useState } from 'react'
import type { GeneratedDocument } from '@af/core'
import { api } from '../lib/api'
import { Card, Empty, IconButton, PageHeader, Spinner, useToast } from '../components/ui'
import { Icon } from '../components/icons'

const KIND_LABEL: Record<GeneratedDocument['kind'], string> = {
  timesheet: 'Timesheet',
  invoice: 'Invoice',
  expense: 'Expense',
}
const KIND_STYLE: Record<GeneratedDocument['kind'], string> = {
  timesheet: 'bg-sky-100 text-sky-700',
  invoice: 'bg-emerald-100 text-emerald-700',
  expense: 'bg-amber-100 text-amber-700',
}

const kb = (n: number) => `${(n / 1024).toFixed(1)} KB`
const when = (iso: string) => iso.slice(0, 16).replace('T', ' ')

export default function Archive() {
  const notify = useToast()
  const [docs, setDocs] = useState<GeneratedDocument[] | null>(null)
  const [q, setQ] = useState('')
  const [kind, setKind] = useState<'all' | GeneratedDocument['kind']>('all')

  useEffect(() => {
    api.listArchive().then(setDocs).catch((e) => notify('err', String(e)))
  }, [notify])

  const del = async (d: GeneratedDocument) => {
    if (!window.confirm(`Delete ${d.filename}? This permanently removes the file.`)) return
    try {
      await api.deleteArchive(d.id)
      setDocs((prev) => (prev ? prev.filter((x) => x.id !== d.id) : prev))
      notify('ok', 'Document deleted')
    } catch (e) {
      notify('err', String(e))
    }
  }

  const rename = async (d: GeneratedDocument) => {
    const title = window.prompt('Rename document (the file on disk is unchanged):', d.title)?.trim()
    if (!title || title === d.title) return
    try {
      const updated = await api.renameArchive(d.id, title)
      setDocs((prev) => (prev ? prev.map((x) => (x.id === d.id ? updated : x)) : prev))
      notify('ok', 'Document renamed')
    } catch (e) {
      notify('err', String(e))
    }
  }

  const filtered = useMemo(() => {
    if (!docs) return []
    const needle = q.trim().toLowerCase()
    return docs.filter(
      (d) =>
        (kind === 'all' || d.kind === kind) &&
        (needle === '' || `${d.title} ${d.filename} ${d.number ?? ''} ${d.periodKey ?? ''}`.toLowerCase().includes(needle)),
    )
  }, [docs, q, kind])

  if (!docs) return <Spinner />

  return (
    <>
      <PageHeader
        title="Document archive"
        subtitle={`${docs.length} generated document${docs.length === 1 ? '' : 's'}`}
        actions={
          <div className="flex items-center gap-2">
            <select className="input w-36" value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
              <option value="all">All types</option>
              <option value="timesheet">Timesheets</option>
              <option value="invoice">Invoices</option>
              <option value="expense">Expenses</option>
            </select>
            <input className="input w-56" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
        }
      />

      <Card>
        {filtered.length === 0 ? (
          <Empty>No documents match.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px]">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="th">Type</th>
                  <th className="th">Title</th>
                  <th className="th">Format</th>
                  <th className="th">Version</th>
                  <th className="th">Size</th>
                  <th className="th">Generated</th>
                  <th className="th text-right">Download</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.map((d) => (
                  <tr key={d.id} className="hover:bg-slate-50">
                    <td className="td">
                      <span className={`pill ${KIND_STYLE[d.kind]}`}>{KIND_LABEL[d.kind]}</span>
                    </td>
                    <td className="td font-medium">{d.title}</td>
                    <td className="td uppercase text-ink-500">{d.format}</td>
                    <td className="td tabular-nums">v{d.version}</td>
                    <td className="td tabular-nums text-ink-500">{kb(d.sizeBytes)}</td>
                    <td className="td whitespace-nowrap text-ink-500">{when(d.createdAt)}</td>
                    <td className="td">
                      <div className="flex items-center justify-end gap-1">
                        <a className="btn-ghost btn-sm" href={api.downloadUrl(d.id, d.filename)} download={d.filename}>
                          <Icon name="download" className="h-3.5 w-3.5 text-ink-400" /> Download
                        </a>
                        <IconButton title="Rename document" onClick={() => rename(d)}>
                          <Icon name="edit" className="h-4 w-4" />
                        </IconButton>
                        <IconButton title="Delete document" onClick={() => del(d)}>
                          <Icon name="trash" className="h-4 w-4" />
                        </IconButton>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
