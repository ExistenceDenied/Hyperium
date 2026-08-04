import { useEffect, useState } from 'react'
import type { Customer, Settings as SettingsType, VatTreatment } from '@af/core'
import { VAT_TREATMENTS, vatTreatmentLabel } from '@af/core'
import { api } from '../lib/api'
import { Card, Field, IconButton, PageHeader, Spinner, useToast } from '../components/ui'
import { Icon } from '../components/icons'

const emptyCustomer = (): Customer => ({
  id: crypto.randomUUID(),
  company: '',
  contactPerson: '',
  addressLines: [],
  vatNumber: '',
  email: '',
  defaultDayRate: 0,
  defaultHourlyRate: 0,
  paymentTermsDays: 30,
  vatTreatment: 'standard',
})

export default function Settings() {
  const notify = useToast()
  const [s, setS] = useState<SettingsType | null>(null)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    api.getSettings().then(setS).catch((e) => notify('err', String(e)))
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
  const setCustomer = (id: string, patch: Partial<Customer>) =>
    apply({ ...s, customers: s.customers.map((c) => (c.id === id ? { ...c, ...patch } : c)) })

  const save = async () => {
    setSaving(true)
    try {
      const saved = await api.saveSettings(s)
      setS(saved)
      setDirty(false)
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
            <Field label="Next invoice number">
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
            <button className="btn-ghost btn-sm" onClick={() => apply({ ...s, customers: [...s.customers, emptyCustomer()] })}>
              <Icon name="plus" className="h-3.5 w-3.5" /> Add customer
            </button>
          </div>
          {s.customers.length === 0 ? (
            <p className="text-sm text-ink-500">No customers yet.</p>
          ) : (
            <div className="space-y-4">
              {s.customers.map((c) => (
                <div key={c.id} className="rounded-lg border border-slate-200 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-xs font-medium text-ink-500">{c.company || 'New customer'}</span>
                    <IconButton
                      onClick={() => apply({ ...s, customers: s.customers.filter((x) => x.id !== c.id) })}
                      title="Remove customer"
                    >
                      <Icon name="trash" className="h-4 w-4" />
                    </IconButton>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    <Field label="Company">
                      <input className="input" value={c.company} onChange={(e) => setCustomer(c.id, { company: e.target.value })} />
                    </Field>
                    <Field label="Contact person">
                      <input className="input" value={c.contactPerson} onChange={(e) => setCustomer(c.id, { contactPerson: e.target.value })} />
                    </Field>
                    <Field label="VAT number">
                      <input className="input" value={c.vatNumber} onChange={(e) => setCustomer(c.id, { vatNumber: e.target.value })} />
                    </Field>
                    <Field label="Address">
                      <textarea
                        className="input min-h-[54px]"
                        value={c.addressLines.join('\n')}
                        onChange={(e) => setCustomer(c.id, { addressLines: e.target.value.split('\n').filter((l) => l.length) })}
                      />
                    </Field>
                    <Field label="Email">
                      <input className="input" value={c.email} onChange={(e) => setCustomer(c.id, { email: e.target.value })} />
                    </Field>
                    <Field label="Default day rate (€)">
                      <input type="number" className="input" value={c.defaultDayRate} onChange={(e) => setCustomer(c.id, { defaultDayRate: Number(e.target.value) })} />
                    </Field>
                    <Field label="Default hourly rate (€)">
                      <input type="number" className="input" value={c.defaultHourlyRate} onChange={(e) => setCustomer(c.id, { defaultHourlyRate: Number(e.target.value) })} />
                    </Field>
                    <Field label="Payment terms (days)">
                      <input type="number" className="input" value={c.paymentTermsDays} onChange={(e) => setCustomer(c.id, { paymentTermsDays: Number(e.target.value) })} />
                    </Field>
                    <Field label="VAT treatment">
                      <select
                        className="input"
                        value={c.vatTreatment}
                        onChange={(e) => setCustomer(c.id, { vatTreatment: e.target.value as VatTreatment })}
                      >
                        {VAT_TREATMENTS.map((t) => (
                          <option key={t} value={t}>
                            {vatTreatmentLabel[t]}
                          </option>
                        ))}
                      </select>
                    </Field>
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
    </>
  )
}
