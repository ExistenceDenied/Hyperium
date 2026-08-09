import type { Customer, Invoice } from './entities'
import { invoiceTotals } from './calculators'

const HEADER = [
  'InvoiceNumber',
  'IssueDate',
  'DueDate',
  'Customer',
  'CustomerVat',
  'VatTreatment',
  'Net',
  'VatRate',
  'VatAmount',
  'Gross',
  'StructuredReference',
  'Reference',
  'Status',
] as const

const csvCell = (v: string | number): string => {
  const s = String(v ?? '')
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

/**
 * A generic, import-mappable accounting CSV — one row per invoice (a sales
 * journal). It is produced as a LOCAL file for the owner to import into their
 * accounting system (Exact / Yuki / Odoo). It deliberately does NOT push to any
 * external system: that would need credentials and network egress, which this
 * app never has. Invoices are ordered by (year, seq) for a clean ledger.
 */
export function accountingCsv(invoices: Invoice[], customers: Customer[]): string {
  const byId = new Map(customers.map((c) => [c.id, c]))
  const ordered = invoices.slice().sort((a, b) => a.year - b.year || a.seq - b.seq)
  const rows = ordered.map((inv) => {
    const t = invoiceTotals(inv)
    const c = byId.get(inv.customerId)
    return [
      inv.number,
      inv.date,
      inv.dueDate,
      c?.company ?? '',
      c?.vatNumber ?? '',
      inv.vatTreatment,
      t.subtotal.toFixed(2),
      String(t.vatRatePct),
      t.vatAmount.toFixed(2),
      t.total.toFixed(2),
      inv.structuredReference,
      inv.reference ?? '',
      inv.status,
    ]
  })
  return [HEADER, ...rows].map((r) => r.map(csvCell).join(',')).join('\r\n') + '\r\n'
}
