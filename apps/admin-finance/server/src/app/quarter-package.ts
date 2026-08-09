import JSZip from 'jszip'
import { accountingCsv, expenseTotals, invoiceTotals, periodKey } from '@af/core'
import type { ExpenseNote, Invoice } from '@af/core'
import { customerRepo, expenseRepo, invoiceRepo, settingsRepo } from '../infra/repositories.js'
import { pdfGenerator } from '../infra/pdf.js'

const slug = (s: string) => s.replace(/[^a-z0-9]+/gi, '-').replace(/^-+|-+$/g, '').toLowerCase()
const eur = (n: number) => n.toFixed(2)
const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0)

export interface QuarterPackage {
  filename: string
  bytes: Buffer
  invoiceCount: number
  expenseCount: number
}

/** "2026-Q3" -> the three month prefixes ["2026-07","2026-08","2026-09"]. */
function parseQuarter(q: string): { year: number; quarter: number; prefixes: string[] } {
  const m = /^(\d{4})-Q([1-4])$/.exec(q)
  if (!m) throw new Error('quarter must be formatted YYYY-Qn, n = 1..4 (e.g. 2026-Q3)')
  const year = Number(m[1])
  const quarter = Number(m[2])
  const start = (quarter - 1) * 3 + 1
  const prefixes = [0, 1, 2].map((i) => `${year}-${String(start + i).padStart(2, '0')}`)
  return { year, quarter, prefixes }
}

function vatSummary(
  year: number,
  quarter: number,
  prefixes: string[],
  invoices: Invoice[],
  expenses: ExpenseNote[],
  companyName: string,
): string {
  const lines: string[] = []
  lines.push(`VAT summary — ${year} Q${quarter} (${prefixes[0]} … ${prefixes[2]})`)
  lines.push(`Company: ${companyName}`)
  lines.push('')
  lines.push(['Month', 'NetRevenue', 'VatCollected', 'VatDeductible'].join('\t'))
  let tNet = 0
  let tColl = 0
  let tDed = 0
  for (const p of prefixes) {
    const mi = invoices.filter((i) => i.date.startsWith(p))
    const net = sum(mi.map((i) => invoiceTotals(i).subtotal))
    const coll = sum(mi.map((i) => invoiceTotals(i).vatAmount))
    const me = expenses.filter((e) => periodKey(e.period) === p)
    const ded = sum(me.map((e) => expenseTotals(e).reimbursementsVat))
    tNet += net
    tColl += coll
    tDed += ded
    lines.push([p, eur(net), eur(coll), eur(ded)].join('\t'))
  }
  lines.push(['Quarter', eur(tNet), eur(tColl), eur(tDed)].join('\t'))
  lines.push('')
  lines.push(`VAT balance (collected − deductible): ${eur(tColl - tDed)}`)
  lines.push(`Invoices: ${invoices.length}   Expense notes: ${expenses.length}`)
  lines.push('')
  lines.push('Prepared locally for hand-off to the accountant — this is not a filed return.')
  return lines.join('\r\n') + '\r\n'
}

/**
 * Bundle everything an accountant needs for a quarter's VAT processing into a
 * single local ZIP: every invoice + expense-note PDF, the accounting CSV (sales
 * journal), and a VAT summary. Produced locally for the owner to hand over — it
 * is never sent anywhere.
 */
export async function buildQuarterPackage(q: string): Promise<QuarterPackage> {
  const { year, quarter, prefixes } = parseQuarter(q)
  const settings = await settingsRepo.get()
  const customers = await customerRepo.list()
  const invoices = (await invoiceRepo.list()).filter((i) => prefixes.some((p) => i.date.startsWith(p)))
  const expenses = (await expenseRepo.list()).filter((e) => prefixes.includes(periodKey(e.period)))

  const zip = new JSZip()
  for (const inv of invoices) {
    zip.file(`invoices/invoice-${slug(inv.number)}.pdf`, await pdfGenerator.invoice(inv, settings, customers))
  }
  for (const e of expenses) {
    zip.file(`expenses/expense-${periodKey(e.period)}.pdf`, await pdfGenerator.expense(e, settings, customers))
  }
  zip.file(`accounting-${year}-Q${quarter}.csv`, accountingCsv(invoices, customers))
  zip.file(
    `vat-summary-${year}-Q${quarter}.txt`,
    vatSummary(year, quarter, prefixes, invoices, expenses, settings.company?.name ?? ''),
  )

  const bytes = await zip.generateAsync({ type: 'nodebuffer' })
  return {
    filename: `quarter-package-${year}-Q${quarter}.zip`,
    bytes,
    invoiceCount: invoices.length,
    expenseCount: expenses.length,
  }
}
