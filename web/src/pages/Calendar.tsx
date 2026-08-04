import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { DocStatus, ExpenseNote, Invoice, Timesheet } from '@af/core'
import {
  DOC_STATUSES,
  formatEUR,
  formatKm,
  invoiceTotals,
  isWeekend,
  isoDate,
  isoWeekday,
  monthDays,
  parsePeriodKey,
  periodKey,
  reimbursableKm,
} from '@af/core'
import { api } from '../lib/api'
import { usePeriod } from '../state/period'
import { Card, PageHeader, Spinner, useToast } from '../components/ui'
import { STATUS_META } from '../components/DocMeta'
import { Icon, type IconName } from '../components/icons'

type EventKind = 'invoice' | 'timesheet' | 'expense' | 'mileage'
interface CalEvent {
  date: string
  kind: EventKind
  status: DocStatus
  label: string
  to: string
  period?: string
}

const KIND_ICON: Record<EventKind, IconName> = { invoice: 'invoice', timesheet: 'calendar', expense: 'expenses', mileage: 'expenses' }
const KIND_LABEL: Record<EventKind, string> = { invoice: 'Invoice', timesheet: 'Timesheet', expense: 'Expense', mileage: 'Mileage' }
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const todayISO = () => new Date().toISOString().slice(0, 10)

export default function CalendarPage() {
  const { key, setKey, label } = usePeriod()
  const notify = useToast()
  const navigate = useNavigate()
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [timesheets, setTimesheets] = useState<Timesheet[]>([])
  const [expenses, setExpenses] = useState<ExpenseNote[]>([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    Promise.all([api.listInvoices(), api.listTimesheets(), api.listExpenses()])
      .then(([i, t, e]) => {
        setInvoices(i)
        setTimesheets(t)
        setExpenses(e)
        setLoaded(true)
      })
      .catch((err) => notify('err', String(err)))
  }, [notify])

  const byDate = useMemo(() => {
    const evs: CalEvent[] = []
    for (const inv of invoices) {
      const total = invoiceTotals(inv).total
      if (inv.date.slice(0, 7) === key)
        evs.push({ date: inv.date, kind: 'invoice', status: inv.status, label: `${inv.number} issued`, to: '/invoices' })
      if (inv.dueDate.slice(0, 7) === key)
        evs.push({ date: inv.dueDate, kind: 'invoice', status: inv.status, label: `${inv.number} due · ${formatEUR(total)}`, to: '/invoices' })
    }
    for (const ts of timesheets) {
      if (periodKey(ts.period) !== key) continue
      for (const d of ts.days)
        evs.push({
          date: d.date,
          kind: 'timesheet',
          status: ts.status,
          label: `${d.billable ? 'Billable' : 'Non-billable'} · ${d.hours ?? 8}h`,
          to: '/timesheet',
          period: key,
        })
    }
    for (const e of expenses) {
      if (periodKey(e.period) !== key) continue
      for (const it of e.items)
        evs.push({ date: it.date, kind: 'expense', status: e.status, label: `${it.category || 'Expense'} · ${formatEUR(it.amount)}`, to: '/expenses', period: key })
      for (const tr of e.trips)
        evs.push({ date: tr.date, kind: 'mileage', status: e.status, label: `${tr.departure} → ${tr.destination} · ${formatKm(reimbursableKm(tr))}`, to: '/expenses', period: key })
    }
    const m = new Map<string, CalEvent[]>()
    for (const ev of evs) {
      const arr = m.get(ev.date)
      if (arr) arr.push(ev)
      else m.set(ev.date, [ev])
    }
    return m
  }, [invoices, timesheets, expenses, key])

  if (!loaded) return <Spinner />

  const period = parsePeriodKey(key)
  const days = monthDays(period)
  const lead = isoWeekday(days[0]) - 1
  const today = todayISO()

  const shift = (dir: number) => {
    let { year, month } = parsePeriodKey(key)
    month += dir
    if (month < 1) {
      month = 12
      year -= 1
    } else if (month > 12) {
      month = 1
      year += 1
    }
    setKey(periodKey({ year, month }))
  }
  const openEvent = (ev: CalEvent) => {
    if (ev.period) setKey(ev.period)
    navigate(ev.to)
  }
  const total = [...byDate.values()].reduce((s, a) => s + a.length, 0)

  return (
    <>
      <PageHeader
        title="Calendar"
        subtitle={`${total} event${total === 1 ? '' : 's'} in ${label}`}
        actions={
          <div className="flex items-center gap-1">
            <button className="btn-ghost btn-sm" onClick={() => shift(-1)} aria-label="Previous month">
              <Icon name="chevron-left" className="h-4 w-4" />
            </button>
            <button className="btn-ghost btn-sm" onClick={() => setKey(periodKey({ year: new Date().getFullYear(), month: new Date().getMonth() + 1 }))}>
              Today
            </button>
            <button className="btn-ghost btn-sm" onClick={() => shift(1)} aria-label="Next month">
              <Icon name="chevron-right" className="h-4 w-4" />
            </button>
          </div>
        }
      />

      <Card className="!p-0">
        <div className="grid grid-cols-7 border-b border-slate-200">
          {WEEKDAYS.map((w) => (
            <div key={w} className="px-2 py-2 text-[11px] font-semibold uppercase tracking-wide text-ink-400">
              <span className="hidden sm:inline">{w}</span>
              <span className="sm:hidden">{w.charAt(0)}</span>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7">
          {Array.from({ length: lead }).map((_, i) => (
            <div key={`lead-${i}`} className="min-h-[104px] border-b border-r border-slate-100 bg-slate-50/40" />
          ))}
          {days.map((d, idx) => {
            const iso = isoDate(d)
            const evs = byDate.get(iso) ?? []
            const isToday = iso === today
            const weekend = isWeekend(d)
            const lastCol = (lead + idx) % 7 === 6
            return (
              <div
                key={iso}
                className={`min-h-[104px] border-b border-slate-100 p-1.5 ${lastCol ? '' : 'border-r'} ${weekend ? 'bg-slate-50/40' : ''}`}
              >
                <div className="mb-1 flex justify-end">
                  <span
                    className={`grid h-6 w-6 place-items-center rounded-full text-xs tabular-nums ${
                      isToday ? 'bg-brand-600 font-semibold text-white' : weekend ? 'text-ink-400' : 'text-ink-600'
                    }`}
                  >
                    {d.getDate()}
                  </span>
                </div>
                <div className="space-y-1">
                  {evs.slice(0, 3).map((ev, i) => (
                    <button
                      key={i}
                      onClick={() => openEvent(ev)}
                      title={`${KIND_LABEL[ev.kind]} — ${ev.label}`}
                      className={`flex w-full items-center gap-1 truncate rounded px-1 py-0.5 text-left text-[10.5px] leading-tight transition hover:brightness-95 ${STATUS_META[ev.status].pill}`}
                    >
                      <Icon name={KIND_ICON[ev.kind]} className="h-2.5 w-2.5 shrink-0" />
                      <span className="truncate">{ev.label}</span>
                    </button>
                  ))}
                  {evs.length > 3 && <div className="px-1 text-[10px] font-medium text-ink-400">+{evs.length - 3} more</div>}
                </div>
              </div>
            )
          })}
        </div>
      </Card>

      <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-ink-500">
        <span className="font-medium text-ink-600">Status</span>
        {DOC_STATUSES.map((s) => (
          <span key={s} className="flex items-center gap-1.5">
            <span className={`h-2.5 w-2.5 rounded-full ${STATUS_META[s].dot}`} />
            {STATUS_META[s].label}
          </span>
        ))}
        <span className="ml-2 hidden text-ink-300 sm:inline">·</span>
        <span className="hidden text-ink-500 sm:inline">Icons mark the entry type (invoice, timesheet, expense, mileage).</span>
      </div>
    </>
  )
}
