import { useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import type { BillingBasis, Comment, Customer, DocStatus, Invoice, InvoiceLine, VatTreatment } from '@af/core'
import { addDaysISO, formatEUR, formatInvoiceNumber, formatNumber, invoiceTotals, lineAmount, VAT_TREATMENTS, vatMention, vatTreatmentLabel } from '@af/core'
import { api } from '../lib/api'
import { usePeriod } from '../state/period'
import { useSettingsCtx } from '../state/settings'
import { Card, Empty, Field, IconButton, PageHeader, Spinner, useToast } from '../components/ui'
import { GenerateButtons } from '../components/GenerateButtons'
import { CustomerModal } from '../components/CustomerModal'
import { DocMeta, StatusBadge } from '../components/DocMeta'
import { Icon } from '../components/icons'

const today = () => new Date().toISOString().slice(0, 10)
type DraftLine = InvoiceLine & { key: string }

export default function Invoices() {
  const notify = useToast()
  const { settings, reload: reloadSettings } = useSettingsCtx()
  const period = usePeriod()
  const location = useLocation()
  const [invoices, setInvoices] = useState<Invoice[] | null>(null)
  const [open, setOpen] = useState<Invoice | null>(null)
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Invoice | null>(null)
  const [custModal, setCustModal] = useState<{ customer: Customer | null } | null>(null)

  // create form state
  const [customerId, setCustomerId] = useState('')
  const [date, setDate] = useState(today())
  const [fromTimesheet, setFromTimesheet] = useState(true)
  const [tsKey, setTsKey] = useState(period.key)
  const [basis, setBasis] = useState<BillingBasis>('day')
  const [vatTreatment, setVatTreatment] = useState<VatTreatment>('standard')
  const [paymentTermsDays, setPaymentTermsDays] = useState(30)
  const [reference, setReference] = useState('')
  const [notes, setNotes] = useState('')
  const [extra, setExtra] = useState<DraftLine[]>([])

  // Pick a customer and adopt its defaults (VAT treatment + payment terms).
  const chooseCustomer = (id: string) => {
    setCustomerId(id)
    const c = settings?.customers.find((x) => x.id === id)
    if (c) {
      setVatTreatment(c.vatTreatment)
      setPaymentTermsDays(c.paymentTermsDays)
    }
  }

  // ---- Inline customer CRUD (persisted via the dedicated /customers endpoints,
  //      which never disturb the invoice counter) --------------------------------
  const openNewCustomer = () => setCustModal({ customer: null })
  const openEditCustomer = () => {
    const c = settings?.customers.find((x) => x.id === customerId)
    if (c) setCustModal({ customer: c })
  }
  const handleCustomerSaved = (saved: Customer, wasNew: boolean) => {
    reloadSettings()
    if (wasNew) chooseCustomer(saved.id) // adopt the brand-new customer for this invoice
    setCustModal(null)
    notify('ok', `Customer ${saved.company} ${wasNew ? 'added' : 'updated'}`)
  }
  const deleteCurrentCustomer = async () => {
    const c = settings?.customers.find((x) => x.id === customerId)
    if (!c) return
    if (!window.confirm(`Delete customer ${c.company}? Existing invoices keep their details; new invoices can't use it.`)) return
    try {
      await api.deleteCustomer(c.id)
      const remaining = (settings?.customers ?? []).filter((x) => x.id !== c.id)
      setCustomerId(remaining[0]?.id ?? '')
      reloadSettings()
      notify('ok', `Customer ${c.company} deleted`)
    } catch (e) {
      notify('err', String(e))
    }
  }

  const load = () => api.listInvoices().then((l) => setInvoices([...l].sort((a, b) => b.number.localeCompare(a.number))))
  useEffect(() => {
    load().catch((e) => notify('err', String(e)))
  }, [notify])
  useEffect(() => {
    if (settings && !customerId && settings.customers[0]) chooseCustomer(settings.customers[0].id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings, customerId])

  // Arriving from the Timesheet's "Generate invoice" — preselect the month and,
  // if all billable days point at one customer, that customer too.
  useEffect(() => {
    const fromKey = (location.state as { fromTimesheetKey?: string } | null)?.fromTimesheetKey
    if (!fromKey || !settings) return
    setFromTimesheet(true)
    setTsKey(fromKey)
    api.timesheetForPeriod(fromKey).then((t) => {
      const ids = [...new Set(t.days.filter((d) => d.billable && d.customerId).map((d) => d.customerId))]
      if (ids.length === 1 && ids[0]) chooseCustomer(ids[0])
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state, settings])

  const customerName = useMemo(
    () => (id: string) => settings?.customers.find((c) => c.id === id)?.company ?? '—',
    [settings],
  )
  const selectedCustomer = useMemo(
    () => settings?.customers.find((c) => c.id === customerId),
    [settings, customerId],
  )

  const create = async () => {
    if (!customerId) return notify('err', 'Pick a customer first')
    setCreating(true)
    try {
      let timesheetId: string | undefined
      if (fromTimesheet) timesheetId = (await api.timesheetForPeriod(tsKey)).id
      const extraLines = extra.map(({ key: _k, ...l }) => l).filter((l) => l.description.trim().length > 0)
      const inv = await api.createInvoice({
        customerId,
        date,
        timesheetId,
        basis,
        vatTreatment,
        paymentTermsDays,
        reference: reference || undefined,
        extraLines,
        notes: notes || undefined,
      })
      notify('ok', `Invoice ${inv.number} created`)
      setNotes('')
      setExtra([])
      await load()
      setOpen(inv)
    } catch (e) {
      notify('err', String(e))
    } finally {
      setCreating(false)
    }
  }

  const patchInvoice = (id: string, patch: { status: DocStatus; comments: Comment[] }) => {
    setInvoices((prev) => (prev ? prev.map((i) => (i.id === id ? { ...i, ...patch } : i)) : prev))
    setOpen((o) => (o && o.id === id ? { ...o, ...patch } : o))
  }
  const del = async (inv: Invoice) => {
    if (!window.confirm(`Delete invoice ${inv.number}? This also removes its generated documents.`)) return
    try {
      await api.deleteDoc('invoice', inv.id)
      setOpen(null)
      await load()
      notify('ok', `Invoice ${inv.number} deleted`)
    } catch (e) {
      notify('err', String(e))
    }
  }

  const duplicate = (inv: Invoice) => {
    setEditing(null)
    chooseCustomer(inv.customerId)
    setVatTreatment(inv.vatTreatment)
    const days = Math.round((Date.parse(inv.dueDate) - Date.parse(inv.date)) / 86_400_000)
    if (Number.isFinite(days) && days >= 0) setPaymentTermsDays(days)
    setReference(inv.reference ?? '')
    setNotes(inv.notes ?? '')
    setFromTimesheet(false)
    setDate(today())
    setExtra(inv.lines.map((l) => ({ key: crypto.randomUUID(), ...l })))
    setOpen(null)
    notify('ok', `Loaded a copy of ${inv.number} — review and create`)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  // Load an existing invoice into the form for editing. Its lines become the
  // editable line items; the number and structured reference stay fixed.
  const startEdit = (inv: Invoice) => {
    setEditing(inv)
    setCustomerId(inv.customerId)
    setVatTreatment(inv.vatTreatment)
    const days = Math.round((Date.parse(inv.dueDate) - Date.parse(inv.date)) / 86_400_000)
    if (Number.isFinite(days) && days >= 0) setPaymentTermsDays(days)
    setReference(inv.reference ?? '')
    setNotes(inv.notes ?? '')
    setFromTimesheet(false)
    setDate(inv.date)
    setExtra(inv.lines.map((l) => ({ key: crypto.randomUUID(), ...l })))
    setOpen(null)
    notify('ok', `Editing ${inv.number} — make changes and save`)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const cancelEdit = () => {
    setEditing(null)
    setExtra([])
    setNotes('')
    setReference('')
    setFromTimesheet(true)
    setDate(today())
    if (settings?.customers[0]) chooseCustomer(settings.customers[0].id)
  }

  const saveEdit = async () => {
    if (!editing) return
    if (!customerId) return notify('err', 'Pick a customer first')
    const lines = extra.map(({ key: _k, ...l }) => l).filter((l) => l.description.trim().length > 0)
    if (lines.length === 0) return notify('err', 'An invoice needs at least one line')
    setCreating(true)
    try {
      const updated = await api.updateInvoice(editing.id, {
        customerId,
        date,
        dueDate: addDaysISO(date, paymentTermsDays),
        lines,
        vatTreatment,
        standardVatRatePct: editing.standardVatRatePct,
        reference: reference || undefined,
        notes: notes || undefined,
      })
      notify('ok', `Invoice ${updated.number} updated`)
      cancelEdit()
      await load()
      setOpen(updated)
    } catch (e) {
      notify('err', String(e))
    } finally {
      setCreating(false)
    }
  }

  if (!invoices || !settings) return <Spinner />

  return (
    <>
      <PageHeader title="Invoices" subtitle="Prepared for owner review — never auto-sent" />

      <Card className="mb-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink-900">
            {editing ? `Edit invoice ${editing.number}` : 'Create invoice'}
          </h2>
          {editing && (
            <button className="btn-ghost btn-sm" onClick={cancelEdit}>
              <Icon name="x" className="h-3.5 w-3.5" /> Cancel edit
            </button>
          )}
        </div>
        {settings.customers.length === 0 ? (
          <Empty>
            <p>You need a customer before you can invoice.</p>
            <button className="btn-ghost btn-sm mt-3 inline-flex" onClick={openNewCustomer}>
              <Icon name="plus" className="h-3.5 w-3.5" /> Add a customer
            </button>
          </Empty>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Customer">
                <div className="flex items-center gap-1.5">
                  <select className="input flex-1" value={customerId} onChange={(e) => chooseCustomer(e.target.value)}>
                    {settings.customers.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.company}
                      </option>
                    ))}
                  </select>
                  <IconButton title="New customer" onClick={openNewCustomer}>
                    <Icon name="plus" className="h-4 w-4" />
                  </IconButton>
                  <IconButton
                    title="Edit selected customer"
                    className="disabled:pointer-events-none disabled:opacity-40"
                    disabled={!customerId}
                    onClick={openEditCustomer}
                  >
                    <Icon name="edit" className="h-4 w-4" />
                  </IconButton>
                  <IconButton
                    title="Delete selected customer"
                    className="disabled:pointer-events-none disabled:opacity-40"
                    disabled={!customerId}
                    onClick={deleteCurrentCustomer}
                  >
                    <Icon name="trash" className="h-4 w-4" />
                  </IconButton>
                </div>
              </Field>
              <Field label="Invoice date">
                <input type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} />
              </Field>
              {!editing && (
                <>
                  <Field label="Bill from timesheet">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-slate-300 text-brand-600"
                        checked={fromTimesheet}
                        onChange={(e) => setFromTimesheet(e.target.checked)}
                      />
                      <select
                        className="input py-1.5"
                        disabled={!fromTimesheet}
                        value={tsKey}
                        onChange={(e) => setTsKey(e.target.value)}
                      >
                        {period.options.map((o) => (
                          <option key={o.key} value={o.key}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </Field>
                  <Field label="Billing basis" hint={basis === 'hour' ? `${formatEUR(selectedCustomer?.defaultHourlyRate ?? 0)}/h` : `${formatEUR(selectedCustomer?.defaultDayRate ?? 0)}/day`}>
                    <select className="input" value={basis} onChange={(e) => setBasis(e.target.value as BillingBasis)}>
                      <option value="day">Per day (day rate)</option>
                      <option value="hour">Per hour (hourly rate)</option>
                    </select>
                  </Field>
                </>
              )}
              <Field label="VAT treatment">
                <select className="input" value={vatTreatment} onChange={(e) => setVatTreatment(e.target.value as VatTreatment)}>
                  {VAT_TREATMENTS.map((t) => (
                    <option key={t} value={t}>
                      {vatTreatmentLabel[t]}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Payment terms (days)">
                <input
                  type="number"
                  min="0"
                  className="input"
                  value={paymentTermsDays}
                  onChange={(e) => setPaymentTermsDays(Math.max(0, Number(e.target.value)))}
                />
              </Field>
              <Field label="Your reference / PO" hint="Printed on the invoice">
                <input className="input" value={reference} placeholder="e.g. PO-2026-042" onChange={(e) => setReference(e.target.value)} />
              </Field>
              <Field label="Notes (optional)" hint="Footer text on the invoice">
                <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
              </Field>
            </div>

            <div className="mt-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs font-medium text-ink-600">{editing ? 'Line items' : 'Extra lines (optional)'}</span>
                <button
                  className="btn-ghost btn-sm"
                  onClick={() => setExtra((x) => [...x, { key: crypto.randomUUID(), description: '', quantity: 1, unit: 'item', unitPrice: 0 }])}
                >
                  <Icon name="plus" className="h-3.5 w-3.5" /> Add line
                </button>
              </div>
              {extra.length > 0 && (
                <div className="space-y-2">
                  {extra.map((l) => (
                    <div key={l.key} className="grid grid-cols-12 items-center gap-2">
                      <input
                        className="input col-span-5"
                        placeholder="Description"
                        value={l.description}
                        onChange={(e) => setExtra((x) => x.map((y) => (y.key === l.key ? { ...y, description: e.target.value } : y)))}
                      />
                      <input
                        type="number"
                        className="input col-span-2"
                        placeholder="Qty"
                        value={l.quantity}
                        onChange={(e) => setExtra((x) => x.map((y) => (y.key === l.key ? { ...y, quantity: Number(e.target.value) } : y)))}
                      />
                      <input
                        className="input col-span-2"
                        placeholder="Unit"
                        value={l.unit}
                        onChange={(e) => setExtra((x) => x.map((y) => (y.key === l.key ? { ...y, unit: e.target.value } : y)))}
                      />
                      <input
                        type="number"
                        className="input col-span-2"
                        placeholder="Unit price"
                        value={l.unitPrice}
                        onChange={(e) => setExtra((x) => x.map((y) => (y.key === l.key ? { ...y, unitPrice: Number(e.target.value) } : y)))}
                      />
                      <div className="col-span-1 flex justify-end">
                        <IconButton onClick={() => setExtra((x) => x.filter((y) => y.key !== l.key))} title="Remove line">
                          <Icon name="trash" className="h-4 w-4" />
                        </IconButton>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-end gap-3">
              {editing ? (
                <span className="text-xs text-ink-500">
                  Number{' '}
                  <span className="font-semibold tabular-nums text-ink-700">{editing.number}</span> · unchanged
                </span>
              ) : (
                <span className="text-xs text-ink-500">
                  Will be numbered{' '}
                  <span className="font-semibold tabular-nums text-ink-700">
                    {formatInvoiceNumber(
                      settings.company.invoiceNumberFormat,
                      Number((fromTimesheet ? tsKey : date).slice(0, 4)),
                      settings.company.nextInvoiceSeq,
                    )}
                  </span>
                </span>
              )}
              {editing && (
                <button className="btn-ghost" onClick={cancelEdit} disabled={creating}>
                  Cancel
                </button>
              )}
              <button className="btn-primary" onClick={editing ? saveEdit : create} disabled={creating}>
                {creating ? 'Saving…' : editing ? 'Save changes' : 'Create invoice'}
              </button>
            </div>
          </>
        )}
      </Card>

      <Card>
        <h2 className="mb-3 text-sm font-semibold text-ink-900">All invoices</h2>
        {invoices.length === 0 ? (
          <Empty>No invoices yet.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px]">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="th">Number</th>
                  <th className="th">Customer</th>
                  <th className="th">Date</th>
                  <th className="th">Due</th>
                  <th className="th text-right">Total</th>
                  <th className="th">Status</th>
                  <th className="th text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {invoices.map((inv) => {
                  const t = invoiceTotals(inv)
                  return (
                    <tr key={inv.id} className="hover:bg-slate-50">
                      <td className="td">
                        <button className="font-medium text-brand-700 hover:underline" onClick={() => setOpen(inv)}>
                          {inv.number}
                        </button>
                      </td>
                      <td className="td">{customerName(inv.customerId)}</td>
                      <td className="td whitespace-nowrap">{inv.date}</td>
                      <td className="td whitespace-nowrap">{inv.dueDate}</td>
                      <td className="td text-right font-medium tabular-nums">{formatEUR(t.total)}</td>
                      <td className="td">
                        <StatusBadge status={inv.status} />
                      </td>
                      <td className="td">
                        <div className="flex items-center justify-end gap-1">
                          <IconButton title="Edit this invoice" onClick={() => startEdit(inv)}>
                            <Icon name="edit" className="h-4 w-4" />
                          </IconButton>
                          <IconButton title="Duplicate this invoice" onClick={() => duplicate(inv)}>
                            <Icon name="copy" className="h-4 w-4" />
                          </IconButton>
                          <GenerateButtons kind="invoice" refId={inv.id} />
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {open && (
        <InvoiceDrawer
          invoice={open}
          customerName={customerName(open.customerId)}
          onClose={() => setOpen(null)}
          onEdit={() => startEdit(open)}
          onDuplicate={() => duplicate(open)}
          onMeta={(patch) => patchInvoice(open.id, patch)}
          onDelete={() => del(open)}
        />
      )}

      {custModal && (
        <CustomerModal initial={custModal.customer} onClose={() => setCustModal(null)} onSaved={handleCustomerSaved} />
      )}
    </>
  )
}

function InvoiceDrawer({
  invoice,
  customerName,
  onClose,
  onEdit,
  onDuplicate,
  onMeta,
  onDelete,
}: {
  invoice: Invoice
  customerName: string
  onClose: () => void
  onEdit: () => void
  onDuplicate: () => void
  onMeta: (patch: { status: DocStatus; comments: Comment[] }) => void
  onDelete: () => void
}) {
  const t = invoiceTotals(invoice)
  const mention = vatMention[invoice.vatTreatment]
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])
  return (
    <div className="fixed inset-0 z-30 flex" role="dialog" aria-modal="true" aria-label={`Invoice ${invoice.number}`}>
      <div className="flex-1 animate-fade-in bg-ink-900/30" onClick={onClose} />
      <div className="flex w-full max-w-lg animate-slide-in-right flex-col overflow-y-auto border-l border-slate-200 bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <div className="text-sm font-semibold text-ink-900">Invoice {invoice.number}</div>
            <div className="text-xs text-ink-500">{customerName}</div>
          </div>
          <IconButton onClick={onClose} title="Close">
            <Icon name="x" className="h-4 w-4" />
          </IconButton>
        </div>
        <div className="space-y-4 px-5 py-4 text-sm">
          <div className="grid grid-cols-2 gap-3 text-ink-700">
            <div>
              <div className="text-xs text-ink-500">Invoice date</div>
              {invoice.date}
            </div>
            <div>
              <div className="text-xs text-ink-500">Due date</div>
              {invoice.dueDate}
            </div>
            <div>
              <div className="text-xs text-ink-500">VAT treatment</div>
              {vatTreatmentLabel[invoice.vatTreatment]}
            </div>
            {invoice.reference && (
              <div>
                <div className="text-xs text-ink-500">Your reference</div>
                {invoice.reference}
              </div>
            )}
            <div className="col-span-2">
              <div className="text-xs text-ink-500">Structured reference</div>
              <span className="font-medium">{invoice.structuredReference}</span>
            </div>
          </div>
          <div>
            <div className="mb-1 text-xs font-medium text-ink-500">Lines</div>
            <table className="w-full">
              <tbody className="divide-y divide-slate-100">
                {invoice.lines.map((l, i) => (
                  <tr key={i}>
                    <td className="py-1.5 pr-2">{l.description}</td>
                    <td className="py-1.5 text-right tabular-nums text-ink-600">
                      {formatNumber(l.quantity)} × {formatEUR(l.unitPrice)}
                    </td>
                    <td className="py-1.5 pl-2 text-right font-medium tabular-nums">{formatEUR(lineAmount(l))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="ml-auto w-56 space-y-1 text-right">
            <div className="flex justify-between text-ink-600">
              <span>Subtotal</span>
              <span className="tabular-nums">{formatEUR(t.subtotal)}</span>
            </div>
            <div className="flex justify-between text-ink-600">
              <span>VAT {formatNumber(t.vatRatePct)}%</span>
              <span className="tabular-nums">{formatEUR(t.vatAmount)}</span>
            </div>
            <div className="flex justify-between border-t border-slate-200 pt-1 font-semibold text-ink-900">
              <span>Total</span>
              <span className="tabular-nums">{formatEUR(t.total)}</span>
            </div>
          </div>
          {mention && <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">{mention}</p>}
          <div className="border-t border-slate-100 pt-4">
            <DocMeta kind="invoice" id={invoice.id} status={invoice.status} comments={invoice.comments} onChange={onMeta} compact />
          </div>
        </div>
        <div className="mt-auto flex items-center justify-between gap-2 border-t border-slate-200 px-5 py-4">
          <div className="flex items-center gap-2">
            <button className="btn-ghost btn-sm" onClick={onEdit}>
              <Icon name="edit" className="h-3.5 w-3.5" /> Edit
            </button>
            <button className="btn-ghost btn-sm" onClick={onDuplicate}>
              <Icon name="copy" className="h-3.5 w-3.5" /> Duplicate
            </button>
            <button className="btn-ghost btn-sm text-rose-600 hover:bg-rose-50" onClick={onDelete}>
              <Icon name="trash" className="h-3.5 w-3.5" /> Delete
            </button>
          </div>
          <GenerateButtons kind="invoice" refId={invoice.id} />
        </div>
      </div>
    </div>
  )
}
