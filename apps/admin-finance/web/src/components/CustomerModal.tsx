import { useEffect, useState } from 'react'
import type { Customer, VatTreatment } from '@af/core'
import { VAT_TREATMENTS, vatTreatmentLabel } from '@af/core'
import { api } from '../lib/api'
import { Field, IconButton, useToast } from './ui'
import { Icon } from './icons'

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

/**
 * Create or edit a single customer without leaving the current page. `initial`
 * null = new customer. Persists via the dedicated customer endpoints (which do
 * not touch the invoice counter), then hands the saved record back to the parent.
 */
export function CustomerModal({
  initial,
  onClose,
  onSaved,
}: {
  initial: Customer | null
  onClose: () => void
  onSaved: (c: Customer, wasNew: boolean) => void
}) {
  const notify = useToast()
  const wasNew = initial == null
  const [c, setC] = useState<Customer>(initial ?? emptyCustomer())
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])

  const set = <K extends keyof Customer>(k: K, v: Customer[K]) => setC((prev) => ({ ...prev, [k]: v }))

  const save = async () => {
    if (!c.company.trim()) return notify('err', 'Company name is required')
    setSaving(true)
    try {
      const saved = wasNew ? await api.createCustomer(c) : await api.updateCustomer(c)
      onSaved(saved, wasNew)
    } catch (e) {
      notify('err', String(e))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label={wasNew ? 'New customer' : `Edit ${c.company}`}>
      <div className="absolute inset-0 animate-fade-in bg-ink-900/30" onClick={onClose} />
      <div className="relative z-10 flex max-h-[90vh] w-full max-w-lg animate-rise-in flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div className="text-sm font-semibold text-ink-900">{wasNew ? 'New customer' : `Edit ${initial?.company || 'customer'}`}</div>
          <IconButton onClick={onClose} title="Close">
            <Icon name="x" className="h-4 w-4" />
          </IconButton>
        </div>

        <div className="grid gap-3 overflow-y-auto px-5 py-4 sm:grid-cols-2">
          <Field label="Company">
            <input className="input" value={c.company} autoFocus onChange={(e) => set('company', e.target.value)} />
          </Field>
          <Field label="Contact person">
            <input className="input" value={c.contactPerson} onChange={(e) => set('contactPerson', e.target.value)} />
          </Field>
          <Field label="VAT number">
            <input className="input" value={c.vatNumber} placeholder="BE0123.456.789" onChange={(e) => set('vatNumber', e.target.value)} />
          </Field>
          <Field label="Email">
            <input className="input" value={c.email} onChange={(e) => set('email', e.target.value)} />
          </Field>
          <Field label="Address (one line per row)">
            <textarea
              className="input min-h-[54px]"
              value={c.addressLines.join('\n')}
              onChange={(e) => set('addressLines', e.target.value.split('\n').filter((l) => l.length))}
            />
          </Field>
          <Field label="VAT treatment">
            <select className="input" value={c.vatTreatment} onChange={(e) => set('vatTreatment', e.target.value as VatTreatment)}>
              {VAT_TREATMENTS.map((t) => (
                <option key={t} value={t}>
                  {vatTreatmentLabel[t]}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Default day rate (€)">
            <input type="number" className="input" value={c.defaultDayRate} onChange={(e) => set('defaultDayRate', Number(e.target.value))} />
          </Field>
          <Field label="Default hourly rate (€)">
            <input type="number" className="input" value={c.defaultHourlyRate} onChange={(e) => set('defaultHourlyRate', Number(e.target.value))} />
          </Field>
          <Field label="Payment terms (days)">
            <input type="number" min="0" className="input" value={c.paymentTermsDays} onChange={(e) => set('paymentTermsDays', Math.max(0, Number(e.target.value)))} />
          </Field>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-slate-200 px-5 py-4">
          <button className="btn-ghost btn-sm" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button className="btn-primary btn-sm" onClick={save} disabled={saving}>
            {saving ? 'Saving…' : wasNew ? 'Add customer' : 'Save customer'}
          </button>
        </div>
      </div>
    </div>
  )
}
