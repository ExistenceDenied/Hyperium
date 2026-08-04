import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Timesheet as TimesheetType, TimesheetDay } from '@af/core'
import { formatNumber, isWeekend, isoDate, isoWeekday, monthDays, monthLabel, parsePeriodKey, periodKey, timesheetTotals } from '@af/core'
import { api } from '../lib/api'
import { usePeriod } from '../state/period'
import { Card, Empty, PageHeader, Spinner, StatTile, useToast } from '../components/ui'
import { GenerateButtons } from '../components/GenerateButtons'
import { CopyFrom } from '../components/CopyFrom'
import { DocMeta } from '../components/DocMeta'
import { Icon } from '../components/icons'
import { useSettings } from '../state/settings'

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const rowInputBase =
  'rounded-md border border-slate-200 bg-white px-2 py-1 text-[13px] text-ink-800 transition-colors placeholder:text-slate-300 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500/20'
const rowInput = `${rowInputBase} w-full`
const rowInputHours = `${rowInputBase} w-14 text-right tabular-nums`

export default function Timesheet() {
  const { key, label } = usePeriod()
  const notify = useToast()
  const navigate = useNavigate()
  const settings = useSettings()
  const [ts, setTs] = useState<TimesheetType | null>(null)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [sources, setSources] = useState<TimesheetType[]>([])

  useEffect(() => {
    setTs(null)
    setDirty(false)
    api.timesheetForPeriod(key).then(setTs).catch((e) => notify('err', String(e)))
    api
      .listTimesheets()
      .then((list) => setSources(list.filter((t) => t.days.length > 0 && periodKey(t.period) !== key)))
      .catch(() => setSources([]))
  }, [key, notify])

  const totals = useMemo(() => (ts ? timesheetTotals(ts) : null), [ts])
  const dayMap = useMemo(() => new Map((ts?.days ?? []).map((d) => [d.date, d])), [ts])

  const update = useCallback((days: TimesheetDay[]) => {
    setTs((prev) => (prev ? { ...prev, days } : prev))
    setDirty(true)
  }, [])

  if (!ts || !totals) return <Spinner />

  const toggleDay = (date: string) => {
    if (dayMap.has(date)) update(ts.days.filter((d) => d.date !== date))
    else update([...ts.days, { date, billable: true, hours: 8 }])
  }
  const patchDay = (date: string, patch: Partial<TimesheetDay>) =>
    update(ts.days.map((d) => (d.date === date ? { ...d, ...patch } : d)))

  const copyFrom = (srcKey: string) => {
    const src = sources.find((s) => periodKey(s.period) === srcKey)
    if (!src) return
    if (ts.days.length > 0 && !window.confirm(`Replace the ${label} entries with a copy of ${monthLabel(src.period)}?`)) return
    const dim = monthDays(parsePeriodKey(key)).length
    const seen = new Set<string>()
    const days: TimesheetDay[] = []
    for (const d of [...src.days].sort((a, b) => a.date.localeCompare(b.date))) {
      const dom = Math.min(Number(d.date.slice(8, 10)), dim)
      const date = `${key}-${String(dom).padStart(2, '0')}`
      if (seen.has(date)) continue
      seen.add(date)
      days.push({ ...d, date })
    }
    update(days)
    notify('ok', `Copied ${days.length} day${days.length === 1 ? '' : 's'} from ${monthLabel(src.period)} — review and save`)
  }

  const save = async () => {
    setSaving(true)
    try {
      const saved = await api.saveTimesheet(ts)
      setTs(saved)
      setDirty(false)
      notify('ok', 'Timesheet saved')
    } catch (e) {
      notify('err', String(e))
    } finally {
      setSaving(false)
    }
  }
  const del = async () => {
    if (!window.confirm(`Delete the ${label} timesheet? This clears its entries and any generated documents.`)) return
    try {
      await api.deleteDoc('timesheet', ts.id)
      setTs(await api.timesheetForPeriod(key))
      setDirty(false)
      notify('ok', 'Timesheet deleted')
    } catch (e) {
      notify('err', String(e))
    }
  }

  const days = monthDays(parsePeriodKey(key))
  const lead = isoWeekday(days[0]) - 1
  const sortedDays = [...ts.days].sort((a, b) => a.date.localeCompare(b.date))

  return (
    <>
      <PageHeader
        title="Timesheet"
        subtitle={label}
        actions={
          <>
            {dirty && <span className="text-xs text-amber-600">Unsaved changes</span>}
            <button className="btn-primary" onClick={save} disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>
            <GenerateButtons kind="timesheet" refId={ts.id} disabled={dirty} disabledHint="Save first" />
            <button className="btn-ghost btn-sm" onClick={del} title="Delete this timesheet">
              <Icon name="trash" className="h-3.5 w-3.5 text-rose-500" />
            </button>
          </>
        }
      />

      <div className="mb-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Billable days" value={String(totals.billableDays)} hint={`${formatNumber(totals.billableHours, 1)} h`} />
        <StatTile label="Non-billable days" value={String(totals.nonBillableDays)} hint={`${formatNumber(totals.nonBillableHours, 1)} h`} />
        <StatTile label="Total worked" value={String(totals.totalWorkedDays)} hint="days" />
        <StatTile label="Total hours" value={formatNumber(totals.totalHours, 1)} />
      </div>

      <Card className="mb-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm">
            <div className="font-medium text-ink-800">Generate from this month</div>
            <div className="text-xs text-ink-500">Bill the timesheet, or open the month's expense note.</div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              className="btn-ghost btn-sm"
              onClick={() => {
                if (dirty) return notify('err', 'Save the timesheet first')
                navigate('/invoices', { state: { fromTimesheetKey: key } })
              }}
            >
              <Icon name="invoice" className="h-3.5 w-3.5 text-ink-400" /> Generate invoice
            </button>
            <button className="btn-ghost btn-sm" onClick={() => navigate('/expenses')}>
              <Icon name="expenses" className="h-3.5 w-3.5 text-ink-400" /> Open expense note
            </button>
          </div>
        </div>
      </Card>

      <div className="mb-5">
        <DocMeta kind="timesheet" id={ts.id} status={ts.status} comments={ts.comments} onChange={(m) => setTs({ ...ts, ...m })} />
      </div>

      <CopyFrom
        noun="timesheet"
        targetLabel={label}
        sources={sources.map((s) => ({ key: periodKey(s.period), label: monthLabel(s.period) }))}
        onCopy={copyFrom}
      />

      <div className="grid items-start gap-5 lg:grid-cols-[248px_minmax(0,1fr)]">
        <Card>
          <p className="mb-2.5 text-xs text-ink-500">Click a day to register it. Billable by default.</p>
          <div className="grid grid-cols-7 gap-1">
            {WEEKDAYS.map((w, i) => (
              <div key={i} className="pb-0.5 text-center text-[10px] font-semibold uppercase tracking-wide text-ink-400">
                {w.charAt(0)}
              </div>
            ))}
            {Array.from({ length: lead }).map((_, i) => (
              <div key={`lead-${i}`} className="h-8" />
            ))}
            {days.map((d) => {
              const iso = isoDate(d)
              const entry = dayMap.get(iso)
              const weekend = isWeekend(d)
              return (
                <button
                  key={iso}
                  onClick={() => toggleDay(iso)}
                  className={`h-8 rounded-md border text-[13px] tabular-nums transition-colors ${
                    entry
                      ? entry.billable
                        ? 'border-brand-600 bg-brand-600 font-medium text-white shadow-sm'
                        : 'border-slate-300 bg-slate-200 font-medium text-ink-700'
                      : weekend
                        ? 'border-transparent bg-slate-50 text-slate-400 hover:border-slate-200'
                        : 'border-slate-200 bg-white text-ink-600 hover:border-brand-300 hover:bg-brand-50'
                  }`}
                  title={entry ? (entry.billable ? 'Billable' : 'Non-billable') : 'Not worked'}
                >
                  {d.getDate()}
                </button>
              )
            })}
          </div>
          <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-ink-600">
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-[3px] bg-brand-600" /> Billable
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-[3px] bg-slate-200 ring-1 ring-inset ring-slate-300" /> Non-billable
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-[3px] bg-slate-50 ring-1 ring-inset ring-slate-200" /> Not worked
            </span>
          </div>
        </Card>

        <Card>
          <h2 className="mb-3 text-sm font-semibold text-ink-900">Registered days</h2>
          {sortedDays.length === 0 ? (
            <Empty>No days registered for {label}. Click dates in the calendar to add them.</Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-[13px]">
                <thead>
                  <tr className="border-b border-slate-200 text-[10px] font-semibold uppercase tracking-wide text-ink-400">
                    <th className="px-2 py-1.5 text-left font-semibold">Date</th>
                    <th className="px-2 py-1.5 text-center font-semibold">Bill.</th>
                    <th className="px-2 py-1.5 text-right font-semibold">Hrs</th>
                    <th className="px-2 py-1.5 text-left font-semibold">Customer</th>
                    <th className="px-2 py-1.5 text-left font-semibold">Project</th>
                    <th className="px-2 py-1.5 text-left font-semibold">Comment</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {sortedDays.map((d) => (
                    <tr key={d.date} className="hover:bg-slate-50/60">
                      <td className="whitespace-nowrap px-2 py-1 font-medium tabular-nums text-ink-700">{d.date.slice(5)}</td>
                      <td className="px-2 py-1 text-center">
                        <input
                          type="checkbox"
                          className="h-3.5 w-3.5 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                          checked={d.billable}
                          title={d.billable ? 'Billable' : 'Non-billable'}
                          onChange={(e) => patchDay(d.date, { billable: e.target.checked })}
                        />
                      </td>
                      <td className="px-1 py-1 text-right">
                        <input
                          type="number"
                          step="0.5"
                          min="0"
                          max="24"
                          className={rowInputHours}
                          value={d.hours ?? 8}
                          onChange={(e) => patchDay(d.date, { hours: Number(e.target.value) })}
                        />
                      </td>
                      <td className="px-1 py-1">
                        <select
                          className={rowInput}
                          value={d.customerId ?? ''}
                          onChange={(e) => patchDay(d.date, { customerId: e.target.value || undefined })}
                        >
                          <option value="">—</option>
                          {settings?.customers.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.company}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-1 py-1">
                        <input
                          className={rowInput}
                          placeholder="—"
                          value={d.project ?? ''}
                          onChange={(e) => patchDay(d.date, { project: e.target.value || undefined })}
                        />
                      </td>
                      <td className="px-1 py-1">
                        <input
                          className={rowInput}
                          placeholder="—"
                          value={d.comment ?? ''}
                          onChange={(e) => patchDay(d.date, { comment: e.target.value || undefined })}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </>
  )
}
