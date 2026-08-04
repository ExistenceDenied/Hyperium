import { useEffect, useMemo, useState } from 'react'
import type { ExpenseItem, ExpenseNote, MileageTrip } from '@af/core'
import { expenseTotals, formatEUR, formatKm, monthDays, monthLabel, parsePeriodKey, periodKey, reimbursableKm, tripReimbursement } from '@af/core'
import { api } from '../lib/api'
import { usePeriod } from '../state/period'
import { useCustomers } from '../state/settings'
import { Card, Empty, IconButton, PageHeader, Spinner, StatTile, useToast } from '../components/ui'
import { GenerateButtons } from '../components/GenerateButtons'
import { CopyFrom } from '../components/CopyFrom'
import { DocMeta } from '../components/DocMeta'
import { Icon } from '../components/icons'

const iso = (period: { year: number; month: number }) => `${period.year}-${String(period.month).padStart(2, '0')}-01`

export default function Expenses() {
  const { key, label } = usePeriod()
  const notify = useToast()
  const customers = useCustomers()
  const [note, setNote] = useState<ExpenseNote | null>(null)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [sources, setSources] = useState<ExpenseNote[]>([])

  useEffect(() => {
    setNote(null)
    setDirty(false)
    api.expenseForPeriod(key).then(setNote).catch((e) => notify('err', String(e)))
    api
      .listExpenses()
      .then((list) => setSources(list.filter((e) => (e.items.length > 0 || e.trips.length > 0) && periodKey(e.period) !== key)))
      .catch(() => setSources([]))
  }, [key, notify])

  const totals = useMemo(() => (note ? expenseTotals(note) : null), [note])
  if (!note || !totals) return <Spinner />

  const patch = (p: Partial<ExpenseNote>) => {
    setNote({ ...note, ...p })
    setDirty(true)
  }
  const addItem = () =>
    patch({
      items: [
        ...note.items,
        { id: crypto.randomUUID(), date: iso(note.period), category: '', description: '', supplier: '', amount: 0, vatAmount: 0, status: 'draft' },
      ],
    })
  const setItem = (id: string, p: Partial<ExpenseItem>) =>
    patch({ items: note.items.map((i) => (i.id === id ? { ...i, ...p } : i)) })
  const addTrip = () =>
    patch({
      trips: [
        ...note.trips,
        { id: crypto.randomUUID(), date: iso(note.period), departure: '', destination: '', purpose: '', distanceKm: 0, roundTrip: false },
      ],
    })
  const setTrip = (id: string, p: Partial<MileageTrip>) =>
    patch({ trips: note.trips.map((t) => (t.id === id ? { ...t, ...p } : t)) })

  const copyFrom = (srcKey: string) => {
    const src = sources.find((s) => periodKey(s.period) === srcKey)
    if (!src) return
    if ((note.items.length > 0 || note.trips.length > 0) && !window.confirm(`Replace the ${label} entries with a copy of ${monthLabel(src.period)}?`)) return
    const dim = monthDays(parsePeriodKey(key)).length
    const remap = (d: string) => `${key}-${String(Math.min(Number(d.slice(8, 10)), dim)).padStart(2, '0')}`
    const items = src.items.map((i) => ({ ...i, id: crypto.randomUUID(), date: remap(i.date) }))
    const trips = src.trips.map((t) => ({ ...t, id: crypto.randomUUID(), date: remap(t.date) }))
    patch({ items, trips })
    notify('ok', `Copied ${items.length} item${items.length === 1 ? '' : 's'} and ${trips.length} trip${trips.length === 1 ? '' : 's'} from ${monthLabel(src.period)} — review and save`)
  }

  const save = async () => {
    setSaving(true)
    try {
      const saved = await api.saveExpense(note)
      setNote(saved)
      setDirty(false)
      notify('ok', 'Expense note saved')
    } catch (e) {
      notify('err', String(e))
    } finally {
      setSaving(false)
    }
  }
  const del = async () => {
    if (!window.confirm(`Delete the ${label} expense note? This clears its items and any generated documents.`)) return
    try {
      await api.deleteDoc('expense', note.id)
      setNote(await api.expenseForPeriod(key))
      setDirty(false)
      notify('ok', 'Expense note deleted')
    } catch (e) {
      notify('err', String(e))
    }
  }

  return (
    <>
      <PageHeader
        title="Expense note"
        subtitle={label}
        actions={
          <>
            {dirty && <span className="text-xs text-amber-600">Unsaved changes</span>}
            <button className="btn-primary" onClick={save} disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>
            <GenerateButtons kind="expense" refId={note.id} disabled={dirty} disabledHint="Save first" />
            <button className="btn-ghost btn-sm" onClick={del} title="Delete this expense note">
              <Icon name="trash" className="h-3.5 w-3.5 text-rose-500" />
            </button>
          </>
        }
      />

      <div className="mb-5 grid gap-4 sm:grid-cols-4">
        <StatTile label="Reimbursements" value={formatEUR(totals.reimbursementsTotal)} />
        <StatTile label="Mileage" value={formatKm(totals.mileageKm)} hint={formatEUR(totals.mileageReimbursement)} />
        <StatTile label="VAT deductible" value={formatEUR(totals.reimbursementsVat)} />
        <StatTile label="Total" value={formatEUR(totals.grandTotal)} />
      </div>

      <CopyFrom
        noun="expense note"
        targetLabel={label}
        sources={sources.map((s) => ({ key: periodKey(s.period), label: monthLabel(s.period) }))}
        onCopy={copyFrom}
      />

      <div className="mb-5">
        <DocMeta kind="expense" id={note.id} status={note.status} comments={note.comments} onChange={(m) => setNote({ ...note, ...m })} />
      </div>

      <Card className="mb-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink-900">Reimbursements</h2>
          <button className="btn-ghost btn-sm" onClick={addItem}>
            <Icon name="plus" className="h-3.5 w-3.5" /> Add item
          </button>
        </div>
        {note.items.length === 0 ? (
          <Empty>No reimbursements.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px]">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="th">Date</th>
                  <th className="th">Category</th>
                  <th className="th">Description</th>
                  <th className="th">Supplier</th>
                  <th className="th text-right">Amount</th>
                  <th className="th text-right">VAT</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {note.items.map((i) => (
                  <tr key={i.id}>
                    <td className="td"><input type="date" className="input py-1.5" value={i.date} onChange={(e) => setItem(i.id, { date: e.target.value })} /></td>
                    <td className="td"><input className="input py-1.5" value={i.category} onChange={(e) => setItem(i.id, { category: e.target.value })} /></td>
                    <td className="td"><input className="input py-1.5" value={i.description} onChange={(e) => setItem(i.id, { description: e.target.value })} /></td>
                    <td className="td"><input className="input py-1.5" value={i.supplier} onChange={(e) => setItem(i.id, { supplier: e.target.value })} /></td>
                    <td className="td"><input type="number" step="0.01" className="input py-1.5 text-right" value={i.amount} onChange={(e) => setItem(i.id, { amount: Number(e.target.value) })} /></td>
                    <td className="td"><input type="number" step="0.01" className="input py-1.5 text-right" value={i.vatAmount} onChange={(e) => setItem(i.id, { vatAmount: Number(e.target.value) })} /></td>
                    <td className="td"><IconButton onClick={() => patch({ items: note.items.filter((x) => x.id !== i.id) })} title="Remove"><Icon name="trash" className="h-4 w-4" /></IconButton></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-ink-900">Mileage</h2>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-xs text-ink-600">
              Rate €/km
              <input
                type="number"
                step="0.0001"
                className="input w-24 py-1.5"
                value={note.mileageRatePerKm}
                onChange={(e) => patch({ mileageRatePerKm: Number(e.target.value) })}
              />
            </label>
            <button className="btn-ghost btn-sm" onClick={addTrip}>
              <Icon name="plus" className="h-3.5 w-3.5" /> Add trip
            </button>
          </div>
        </div>
        {note.trips.length === 0 ? (
          <Empty>No trips.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px]">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="th">Date</th>
                  <th className="th">From</th>
                  <th className="th">To</th>
                  <th className="th">Purpose</th>
                  <th className="th">Client</th>
                  <th className="th text-right">Km</th>
                  <th className="th text-center">Round&nbsp;trip</th>
                  <th className="th text-right">€</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {note.trips.map((t) => (
                  <tr key={t.id}>
                    <td className="td"><input type="date" className="input py-1.5" value={t.date} onChange={(e) => setTrip(t.id, { date: e.target.value })} /></td>
                    <td className="td"><input className="input py-1.5" value={t.departure} onChange={(e) => setTrip(t.id, { departure: e.target.value })} /></td>
                    <td className="td"><input className="input py-1.5" value={t.destination} onChange={(e) => setTrip(t.id, { destination: e.target.value })} /></td>
                    <td className="td"><input className="input py-1.5" value={t.purpose} onChange={(e) => setTrip(t.id, { purpose: e.target.value })} /></td>
                    <td className="td">
                      <select className="input py-1.5" value={t.customerId ?? ''} onChange={(e) => setTrip(t.id, { customerId: e.target.value || undefined })}>
                        <option value="">—</option>
                        {customers.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.company}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="td"><input type="number" className="input py-1.5 text-right" value={t.distanceKm} onChange={(e) => setTrip(t.id, { distanceKm: Number(e.target.value) })} /></td>
                    <td className="td text-center">
                      <input type="checkbox" className="h-4 w-4 rounded border-slate-300 text-brand-600" checked={t.roundTrip} onChange={(e) => setTrip(t.id, { roundTrip: e.target.checked })} />
                    </td>
                    <td className="td whitespace-nowrap text-right tabular-nums text-ink-600">
                      {formatKm(reimbursableKm(t))} · {formatEUR(tripReimbursement(t, note.mileageRatePerKm))}
                    </td>
                    <td className="td"><IconButton onClick={() => patch({ trips: note.trips.filter((x) => x.id !== t.id) })} title="Remove"><Icon name="trash" className="h-4 w-4" /></IconButton></td>
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
