import type { ExpenseNote, Invoice } from './entities'
import { invoiceTotals } from './calculators'

// ---------------------------------------------------------------------------
// CODA parsing (Belgian bank statement, CODA 2.x)
//
// A CODA file is fixed-width, one record per 128-char line, keyed by the first
// two chars. We only need the movement records ("2.1", first two chars "21"):
//   idx 31      sign        '0' = credit (money in / income), '1' = debit (out)
//   idx 32..46  amount      15 digits in thousandths of EUR (÷1000)
//   idx 47..52  value date  DDMMYY
//   idx 61      comm type   '0' = free, '1' = structured
//   idx 62..114 communication; when structured, [0:3] = type, [3:15] = the
//               12-digit Belgian structured reference (the +++…+++ OGM/VCS).
//
// Offsets follow the published CODA 2.x layout; validate against a real bank
// file and adjust here if a specific bank differs.
// ---------------------------------------------------------------------------

export interface CodaMovement {
  sign: 'credit' | 'debit'
  amount: number
  valueDate: string
  structuredRef?: string
  communication: string
}

const digits = (s: string): string => s.replace(/\D/g, '')
const ddmmyyToIso = (s: string): string => `20${s.slice(4, 6)}-${s.slice(2, 4)}-${s.slice(0, 2)}`

export function parseCoda(text: string): CodaMovement[] {
  const out: CodaMovement[] = []
  for (const line of text.split(/\r?\n/)) {
    if (line.length < 47 || line[0] !== '2' || line[1] !== '1') continue
    const amount = Number(line.slice(32, 47)) / 1000
    if (!Number.isFinite(amount)) continue
    const commField = line.slice(62, 115)
    const ref = line[61] === '1' ? digits(commField.slice(3, 15)) : ''
    out.push({
      sign: line[31] === '1' ? 'debit' : 'credit',
      amount: Math.round(amount * 100) / 100,
      valueDate: ddmmyyToIso(line.slice(47, 53)),
      structuredRef: ref.length === 12 ? ref : undefined,
      communication: commField.trim(),
    })
  }
  return out
}

// ---------------------------------------------------------------------------
// Reconciliation: match bank movements to invoices (income) and expense items
// (spending), and surface anything without a supporting document.
// ---------------------------------------------------------------------------

export interface ReconciliationReport {
  paidInvoices: { number: string; invoiced: number; paid: number; valueDate: string; amountMatches: boolean }[]
  unpaidInvoices: { number: string; total: number; structuredReference: string }[]
  unexplainedCredits: { amount: number; valueDate: string; communication: string }[]
  matchedExpenses: { supplier: string; description: string; amount: number; valueDate: string }[]
  unexplainedDebits: { amount: number; valueDate: string; communication: string }[]
  totals: {
    credits: number
    debits: number
    invoicesPaid: number
    invoicesUnpaid: number
    creditsUnexplained: number
    debitsMatched: number
    debitsUnexplained: number
  }
}

const near = (a: number, b: number): boolean => Math.abs(a - b) < 0.01
const sum = (xs: number[]): number => Math.round(xs.reduce((a, b) => a + b, 0) * 100) / 100

export function reconcile(
  movements: CodaMovement[],
  invoices: Invoice[],
  expenses: ExpenseNote[],
): ReconciliationReport {
  const invByRef = new Map<string, Invoice>()
  for (const inv of invoices) invByRef.set(digits(inv.structuredReference), inv)
  const matchedInvoiceIds = new Set<string>()

  const credits = movements.filter((m) => m.sign === 'credit')
  const debits = movements.filter((m) => m.sign === 'debit')

  const paidInvoices: ReconciliationReport['paidInvoices'] = []
  const unexplainedCredits: ReconciliationReport['unexplainedCredits'] = []
  for (const m of credits) {
    // Income is matched on the Belgian structured reference — near-waterproof.
    const inv = m.structuredRef ? invByRef.get(m.structuredRef) : undefined
    if (inv) {
      matchedInvoiceIds.add(inv.id)
      const total = invoiceTotals(inv).total
      paidInvoices.push({
        number: inv.number,
        invoiced: total,
        paid: m.amount,
        valueDate: m.valueDate,
        amountMatches: near(total, m.amount),
      })
    } else {
      unexplainedCredits.push({ amount: m.amount, valueDate: m.valueDate, communication: m.communication })
    }
  }

  const unpaidInvoices = invoices
    .filter((inv) => !matchedInvoiceIds.has(inv.id))
    .map((inv) => ({ number: inv.number, total: invoiceTotals(inv).total, structuredReference: inv.structuredReference }))

  // Expenses have no structured reference, so match debits by amount (gross or
  // net) against expense items — a weaker, best-effort match.
  const items = expenses.flatMap((e) =>
    e.items.map((it) => ({
      supplier: it.supplier,
      description: it.description,
      gross: Math.round((it.amount + (it.vatAmount ?? 0)) * 100) / 100,
      net: it.amount,
    })),
  )
  const usedItem = new Set<number>()
  const matchedExpenses: ReconciliationReport['matchedExpenses'] = []
  const unexplainedDebits: ReconciliationReport['unexplainedDebits'] = []
  for (const m of debits) {
    const idx = items.findIndex((it, i) => !usedItem.has(i) && (near(it.gross, m.amount) || near(it.net, m.amount)))
    if (idx >= 0) {
      usedItem.add(idx)
      const it = items[idx]
      matchedExpenses.push({ supplier: it.supplier, description: it.description, amount: m.amount, valueDate: m.valueDate })
    } else {
      unexplainedDebits.push({ amount: m.amount, valueDate: m.valueDate, communication: m.communication })
    }
  }

  return {
    paidInvoices,
    unpaidInvoices,
    unexplainedCredits,
    matchedExpenses,
    unexplainedDebits,
    totals: {
      credits: sum(credits.map((m) => m.amount)),
      debits: sum(debits.map((m) => m.amount)),
      invoicesPaid: matchedInvoiceIds.size,
      invoicesUnpaid: unpaidInvoices.length,
      creditsUnexplained: unexplainedCredits.length,
      debitsMatched: matchedExpenses.length,
      debitsUnexplained: unexplainedDebits.length,
    },
  }
}
