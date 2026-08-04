import { useEffect, useState } from 'react'
import type { Customer, Settings as SettingsType } from '@af/core'
import { formatEUR, vatTreatmentLabel } from '@af/core'
import { api } from '../lib/api'
import { useSettingsCtx } from '../state/settings'
import { CustomerModal } from '../components/CustomerModal'
import { Card, Field, IconButton, PageHeader, Spinner, useToast } from '../components/ui'
import { Icon } from '../components/icons'

export default function Settings() {
  const notify = useToast()
  const { reload: reloadCtx } = useSettingsCtx()
  const [s, setS] = useState<SettingsType | null>(null)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [custModal, setCustModal] = useState<{ customer: Customer | null } | null>(null)
  // The invoice counter as it was when this page loaded — used at save time to
  // tell an untouched field from an intentional change (see save()).
  const [loadedSeq, setLoadedSeq] = useState<number | null>(null)

  useEffect(() => {
    api
      .getSettings()
      .then((v) => {
        setS(v)
        setLoadedSeq(v.company.nextInvoiceSeq)
      })
      .catch((e) => notify('err', String(e)))
  }, [notify])

  if (!s) return <Spinner />

  const apply = (next: SettingsType) => {
    setS(next)
    setDirty(true)
  }
  const company = <K extends keyof SettingsType['company']>(k: K, v: SettingsType['company'][K]) =>
    apply({ ...s, company: { ...s.company, [k]: v } })
  const fin = <K extends keyof SettingsType['financial']>(k: K, v: SettingsType['financial'][K]) =>
    apply({ ...s, financial: { ...s.financial, [k]: v } })

  // Customers persist immediately via the dedicated /customers endpoints, which
  // touch only settings.customers — never the invoice counter. This is separate
  // from the company/financial "Save settings" batch below.
  const onCustomerSaved = (saved: Customer, wasNew: boolean) => {
    setS((prev) =>
      prev
        ? { ...prev, customers: wasNew ? [...prev.customers, saved] : prev.customers.map((c) => (c.id === saved.id ? saved : c)) }
        : prev,
    )
    reloadCtx()
    setCustModal(null)
    notify('ok', `Customer ${saved.company} ${wasNew ? 'added' : 'updated'}`)
  }
  const deleteCustomer = async (c: Customer) => {
    if (!window.confirm(`Delete customer ${c.company}? Existing invoices keep their details; new invoices can't use it.`)) return
    try {
      await api.deleteCustomer(c.id)
      setS((prev) => (prev ? { ...prev, customers: prev.customers.filter((x) => x.id !== c.id) } : prev))
      reloadCtx()
      notify('ok', `Customer ${c.company} deleted`)
    } catch (e) {
      notify('err', String(e))
    }
  }

  const save = async () => {
    setSaving(true)
    try {
      // Re-read server state first. The invoice counter advances on every invoice
      // created since this page loaded; a naive whole-object save would write back
      // the stale value and rewind it, reissuing invoice numbers. Preserve the
      // server's counter unless the owner explicitly edited the field. Customers
      // are owned by their own endpoints, so always take the server's copy.
      const fresh = await api.getSettings()
      const seqTouched = loadedSeq != null && s.company.nextInvoiceSeq !== loadedSeq
      const payload: SettingsType = {
        company: {
          ...s.company,
          nextInvoiceSeq: seqTouched ? s.company.nextInvoiceSeq : fresh.company.nextInvoiceSeq,
        },
        financial: s.financial,
        customers: fresh.customers,
      }
      const saved = await api.saveSettings(payload)
      setS(saved)
      setLoadedSeq(saved.company.nextInvoiceSeq)
      setDirty(false)
      reloadCtx()
      notify('ok', 'Settings saved')
    } catch (e) {
      notify('err', String(e))
    } finally {
      setSaving(false)
    }
  }
  const discard = () => {
    api.getSettings().then((fresh) => {
      setS(fresh)
      setLoadedSeq(fresh.company.nextInvoiceSeq)
      setDirty(false)
      notify('ok', 'Changes discarded')
    })
  }

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="Company, financial defaults and customers"
        actions={
          <>
            {dirty && <span className="text-xs font-medium text-amber-600">Unsaved changes</span>}
            <button className="btn-primary" onClick={save} disabled={saving || !dirty}>
              {saving ? 'Saving…' : 'Save settings'}
            </button>
          </>
        }
      />

      <div className="grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h2 className="mb-4 text-sm font-semibold text-ink-900">Company</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Name">
              <input className="input" value={s.company.name} onChange={(e) => company('name', e.target.value)} />
            </Field>
            <Field label="Legal form">
              <input className="input" value={s.company.legalForm} onChange={(e) => company('legalForm', e.target.value)} />
            </Field>
            <Field label="VAT number">
              <input className="input" value={s.company.vatNumber} onChange={(e) => company('vatNumber', e.target.value)} placeholder="BE0123.456.789" />
            </Field>
            <Field label="Email">
              <input className="input" value={s.company.email} onChange={(e) => company('email', e.target.value)} />
            </Field>
            <Field label="Address (one line per row)">
              <textarea
                className="input min-h-[70px]"
                value={s.company.addressLines.join('\n')}
                onChange={(e) => company('addressLines', e.target.value.split('\n').filter((l) => l.length))}
              />
            </Field>
            <Field label="Phone">
              <input className="input" value={s.company.phone} onChange={(e) => company('phone', e.target.value)} />
            </Field>
            <Field label="IBAN">
              <input className="input" value={s.company.iban} onChange={(e) => company('iban', e.target.value)} />
            </Field>
            <Field label="BIC">
              <input className="input" value={s.company.bic} onChange={(e) => company('bic', e.target.value)} />
            </Field>
            <Field label="Invoice number format" hint="Tokens: {year} {seq} {seq:3}">
              <input className="input" value={s.company.invoiceNumberFormat} onChange={(e) => company('invoiceNumberFormat', e.target.value)} />
            </Field>
            <Field label="Next invoice number" hint="Advances automatically as invoices are created — only change to override">
              <input
                type="number"
                className="input"
                value={s.company.nextInvoiceSeq}
                onChange={(e) => company('nextInvoiceSeq', Math.max(1, Number(e.target.value)))}
              />
            </Field>
          </div>
        </Card>

        <Card>
          <h2 className="mb-4 text-sm font-semibold text-ink-900">Financial defaults</h2>
          <div className="grid gap-3">
            <Field label="Standard VAT rate (%)">
              <input
                type="number"
                className="input"
                value={s.financial.standardVatRatePct}
                onChange={(e) => fin('standardVatRatePct', Number(e.target.value))}
              />
            </Field>
            <Field label="Mileage rate (€/km)" hint="Belgian forfaitary rate — verify the current official value">
              <input
                type="number"
                step="0.0001"
                className="input"
                value={s.financial.mileageRatePerKm}
                onChange={(e) => fin('mileageRatePerKm', Number(e.target.value))}
              />
            </Field>
          </div>
        </Card>
      </div>

      <div className="mt-5">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink-900">Customers</h2>
            <button className="btn-ghost btn-sm" onClick={() => setCustModal({ customer: null })}>
              <Icon name="plus" className="h-3.5 w-3.5" /> New customer
            </button>
          </div>
          {s.customers.length === 0 ? (
            <p className="text-sm text-ink-500">No customers yet.</p>
          ) : (
            <div className="divide-y divide-slate-100">
              {s.customers.map((c) => (
                <div key={c.id} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-ink-900">{c.company || 'Unnamed customer'}</div>
                    <div className="mt-0.5 truncate text-xs text-ink-500">{[c.contactPerson, c.email].filter(Boolean).join(' · ') || '—'}</div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="hidden text-right text-xs text-ink-500 sm:block">
                      <div className="tabular-nums">
                        {formatEUR(c.defaultDayRate)}/day · {formatEUR(c.defaultHourlyRate)}/h
                      </div>
                      <div>
                        {vatTreatmentLabel[c.vatTreatment]} · {c.paymentTermsDays}d terms
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <IconButton title="Edit customer" onClick={() => setCustModal({ customer: c })}>
                        <Icon name="edit" className="h-4 w-4" />
                      </IconButton>
                      <IconButton title="Delete customer" onClick={() => deleteCustomer(c)}>
                        <Icon name="trash" className="h-4 w-4" />
                      </IconButton>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {dirty && (
        <div className="sticky bottom-4 z-10 mt-6 animate-rise-in">
          <div className="mx-auto flex max-w-md items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white/95 px-4 py-3 shadow-lg backdrop-blur">
            <span className="text-sm text-ink-600">You have unsaved changes.</span>
            <div className="flex items-center gap-2">
              <button className="btn-ghost btn-sm" onClick={discard} disabled={saving}>
                Discard
              </button>
              <button className="btn-primary btn-sm" onClick={save} disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {custModal && (
        <CustomerModal initial={custModal.customer} onClose={() => setCustModal(null)} onSaved={onCustomerSaved} />
      )}
    </>
  )
}
