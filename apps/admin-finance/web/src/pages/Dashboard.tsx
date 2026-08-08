import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { DashboardData, GeneratedDocument, Invoice } from '@af/core'
import { formatEUR, invoiceTotals } from '@af/core'
import { api } from '../lib/api'
import { usePeriod } from '../state/period'
import { Card, PageHeader, Spinner, StatTile, useToast } from '../components/ui'
import { Icon, type IconName } from '../components/icons'

interface Prep {
  to: string
  icon: IconName
  title: string
  detail: string
  done: boolean
}

const KIND_STYLE: Record<GeneratedDocument['kind'], string> = {
  timesheet: 'bg-sky-100 text-sky-700',
  invoice: 'bg-emerald-100 text-emerald-700',
  expense: 'bg-amber-100 text-amber-700',
}

export default function Dashboard() {
  const { key, label } = usePeriod()
  const notify = useToast()
  const [data, setData] = useState<DashboardData | null>(null)
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [docs, setDocs] = useState<GeneratedDocument[]>([])

  useEffect(() => {
    setData(null)
    api.dashboard(key).then(setData).catch((e) => notify('err', String(e)))
    api.listInvoices().then((l) => setInvoices(l.filter((i) => i.date.slice(0, 7) === key))).catch(() => setInvoices([]))
    api.listArchive().then((l) => setDocs(l.slice(0, 6))).catch(() => setDocs([]))
  }, [key, notify])

  if (!data) return <Spinner />

  const net = data.vatCollected - data.vatDeductible
  const invoiceTotal = invoices.reduce((s, i) => s + invoiceTotals(i).total, 0)
  const prep: Prep[] = [
    {
      to: '/timesheet',
      icon: 'calendar',
      title: 'Timesheet',
      detail: data.billableDays > 0 ? `${data.billableDays} billable day${data.billableDays === 1 ? '' : 's'} logged` : 'No days logged yet',
      done: data.billableDays > 0,
    },
    {
      to: '/invoices',
      icon: 'invoice',
      title: 'Invoices',
      detail: invoices.length > 0 ? `${invoices.length} invoice${invoices.length === 1 ? '' : 's'} · ${formatEUR(invoiceTotal)}` : 'None prepared yet',
      done: invoices.length > 0,
    },
    {
      to: '/expenses',
      icon: 'expenses',
      title: 'Expense note',
      detail: data.expenses + data.mileageReimbursement > 0 ? formatEUR(data.expenses + data.mileageReimbursement) + ' logged' : 'Nothing logged yet',
      done: data.expenses + data.mileageReimbursement > 0,
    },
  ]

  return (
    <>
      <PageHeader title="Dashboard" subtitle={label} />

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatTile label="Billable days" value={String(data.billableDays)} />
        <StatTile label="Revenue (excl. VAT)" value={formatEUR(data.revenue)} />
        <StatTile label="Expenses" value={formatEUR(data.expenses)} hint="Reimbursements" />
        <StatTile label="Mileage" value={formatEUR(data.mileageReimbursement)} />
        <StatTile label="VAT collected" value={formatEUR(data.vatCollected)} />
        <StatTile label="VAT deductible" value={formatEUR(data.vatDeductible)} />
        <StatTile label="VAT balance" value={formatEUR(net)} hint={net >= 0 ? 'Payable' : 'Recoverable'} />
        <StatTile label="Profit estimate" value={formatEUR(data.profitEstimate)} hint="Rev − exp − mileage" />
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <Card>
          <h2 className="mb-1 text-sm font-semibold text-ink-900">Prepare {label}</h2>
          <p className="mb-4 text-xs text-ink-500">Everything is prepared for your review — nothing is sent automatically.</p>
          <div className="divide-y divide-slate-100">
            {prep.map((p) => (
              <Link key={p.to} to={p.to} className="group flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${p.done ? 'bg-brand-50 text-brand-600' : 'bg-slate-100 text-ink-400'}`}>
                  <Icon name={p.icon} className="h-[18px] w-[18px]" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="text-sm font-medium text-ink-900">{p.title}</span>
                    {p.done && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                        <Icon name="check" className="h-3 w-3" /> Started
                      </span>
                    )}
                  </span>
                  <span className="block truncate text-xs text-ink-500">{p.detail}</span>
                </span>
                <span className="text-ink-300 transition-colors group-hover:text-brand-600">→</span>
              </Link>
            ))}
          </div>
        </Card>

        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink-900">Recent documents</h2>
            <Link to="/archive" className="text-xs font-medium text-brand-700 hover:underline">
              View archive
            </Link>
          </div>
          {docs.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-ink-500">
              No documents generated yet.
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {docs.map((d) => (
                <div key={d.id} className="flex items-center gap-3 py-2.5 first:pt-0 last:pb-0">
                  <span className={`pill ${KIND_STYLE[d.kind]} shrink-0 capitalize`}>{d.kind}</span>
                  <span className="min-w-0 flex-1 truncate text-sm text-ink-800">{d.title}</span>
                  <span className="hidden shrink-0 text-xs text-ink-400 sm:inline">{d.createdAt.slice(0, 10)}</span>
                  <a
                    className="btn-ghost btn-sm shrink-0"
                    href={api.downloadUrl(d.id, d.filename)}
                    download={d.filename}
                    title={`Download ${d.filename}`}
                  >
                    <Icon name="download" className="h-3.5 w-3.5 text-ink-400" />
                    <span className="uppercase">{d.format}</span>
                  </a>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </>
  )
}
