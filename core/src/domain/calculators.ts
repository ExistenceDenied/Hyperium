import { round2, sum } from './money'
import { computeVat, type VatTreatment } from './vat'
import { mileageTotals } from './mileage'
import { referenceSeedFromInvoice, structuredReference } from './structured-reference'
import { addDaysISO, type Period } from './period'
import type { Company, Customer, ExpenseNote, Invoice, InvoiceLine, Timesheet } from './entities'

const monthLabelInline = (p: Period): string =>
  new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric' }).format(new Date(p.year, p.month - 1, 1))

// ---- Timesheet --------------------------------------------------------------
const dayHours = (d: { hours?: number }): number => d.hours ?? 8

export interface TimesheetTotals {
  billableDays: number
  nonBillableDays: number
  totalWorkedDays: number
  billableHours: number
  nonBillableHours: number
  totalHours: number
}
export function timesheetTotals(t: Timesheet): TimesheetTotals {
  const totalWorkedDays = t.days.length
  const billableDays = t.days.filter((d) => d.billable).length
  const billableHours = round2(sum(t.days.filter((d) => d.billable).map(dayHours)))
  const totalHours = round2(sum(t.days.map(dayHours)))
  return {
    billableDays,
    nonBillableDays: totalWorkedDays - billableDays,
    totalWorkedDays,
    billableHours,
    nonBillableHours: round2(totalHours - billableHours),
    totalHours,
  }
}
export function billableDaysByCustomer(t: Timesheet): Map<string, number> {
  const m = new Map<string, number>()
  for (const d of t.days) if (d.billable && d.customerId) m.set(d.customerId, (m.get(d.customerId) ?? 0) + 1)
  return m
}

// ---- Invoice ----------------------------------------------------------------
export const lineAmount = (l: InvoiceLine): number => round2(l.quantity * l.unitPrice)

export interface InvoiceTotals {
  subtotal: number
  vatRatePct: number
  vatAmount: number
  total: number
}
export function invoiceTotals(inv: Pick<Invoice, 'lines' | 'vatTreatment' | 'standardVatRatePct'>): InvoiceTotals {
  const subtotal = sum(inv.lines.map(lineAmount))
  const vat = computeVat(subtotal, inv.vatTreatment, inv.standardVatRatePct)
  return { subtotal, vatRatePct: vat.ratePct, vatAmount: vat.amount, total: round2(subtotal + vat.amount) }
}

export function formatInvoiceNumber(format: string, year: number, seq: number): string {
  return format
    .replace(/\{year\}/g, String(year))
    .replace(/\{seq:(\d+)\}/g, (_m, n: string) => String(seq).padStart(Number(n), '0'))
    .replace(/\{seq\}/g, String(seq))
}

export type BillingBasis = 'day' | 'hour'

export interface BuildInvoiceInput {
  id: string
  year: number
  seq: number
  date: string
  company: Company
  customer: Customer
  timesheet?: Timesheet
  basis?: BillingBasis
  extraLines?: InvoiceLine[]
  standardVatRatePct: number
  vatTreatment?: VatTreatment
  paymentTermsDays?: number
  reference?: string
  notes?: string
  createdAt: string
}

/** Pure builder — assemble an Invoice from a timesheet (by day or by hour) + the customer's rates. */
export function buildInvoice(inp: BuildInvoiceInput): Invoice {
  const basis: BillingBasis = inp.basis ?? 'day'
  const lines: InvoiceLine[] = []
  if (inp.timesheet) {
    const billableDays = inp.timesheet.days.filter(
      (d) => d.billable && (!d.customerId || d.customerId === inp.customer.id),
    )
    const period = monthLabelInline(inp.timesheet.period)
    if (basis === 'hour') {
      const hours = round2(sum(billableDays.map((d) => d.hours ?? 8)))
      if (hours > 0) {
        lines.push({
          description: `Consulting services — ${period} (${hours} billable hour${hours === 1 ? '' : 's'})`,
          quantity: hours,
          unit: 'hour',
          unitPrice: inp.customer.defaultHourlyRate,
        })
      }
    } else if (billableDays.length > 0) {
      lines.push({
        description: `Consulting services — ${period} (${billableDays.length} billable day${billableDays.length === 1 ? '' : 's'})`,
        quantity: billableDays.length,
        unit: 'day',
        unitPrice: inp.customer.defaultDayRate,
      })
    }
  }
  for (const l of inp.extraLines ?? []) lines.push(l)
  const number = formatInvoiceNumber(inp.company.invoiceNumberFormat, inp.year, inp.seq)
  return {
    id: inp.id,
    number,
    seq: inp.seq,
    year: inp.year,
    date: inp.date,
    dueDate: addDaysISO(inp.date, inp.paymentTermsDays ?? inp.customer.paymentTermsDays),
    customerId: inp.customer.id,
    timesheetId: inp.timesheet?.id,
    lines,
    vatTreatment: inp.vatTreatment ?? inp.customer.vatTreatment,
    standardVatRatePct: inp.standardVatRatePct,
    structuredReference: structuredReference(referenceSeedFromInvoice(inp.year, inp.seq)),
    reference: inp.reference,
    notes: inp.notes,
    status: 'draft',
    comments: [],
    createdAt: inp.createdAt,
  }
}

// ---- Expense note -----------------------------------------------------------
export interface ExpenseTotals {
  reimbursementsTotal: number
  reimbursementsVat: number
  mileageKm: number
  mileageReimbursement: number
  grandTotal: number
}
export function expenseTotals(note: ExpenseNote): ExpenseTotals {
  const reimbursementsTotal = sum(note.items.map((i) => i.amount))
  const reimbursementsVat = sum(note.items.map((i) => i.vatAmount ?? 0))
  const m = mileageTotals(note.trips, note.mileageRatePerKm)
  return {
    reimbursementsTotal,
    reimbursementsVat,
    mileageKm: m.totalKm,
    mileageReimbursement: m.totalReimbursement,
    grandTotal: round2(reimbursementsTotal + m.totalReimbursement),
  }
}

// ---- Monthly dashboard ------------------------------------------------------
export interface DashboardData {
  period: Period
  billableDays: number
  revenue: number
  expenses: number
  mileageReimbursement: number
  vatCollected: number
  vatDeductible: number
  profitEstimate: number
}
export interface DashboardInput {
  period: Period
  timesheet?: Timesheet
  invoices: Invoice[]
  expenseNote?: ExpenseNote
}
export function monthlyDashboard(inp: DashboardInput): DashboardData {
  const billableDays = inp.timesheet ? timesheetTotals(inp.timesheet).billableDays : 0
  let revenue = 0
  let vatCollected = 0
  for (const inv of inp.invoices) {
    const t = invoiceTotals(inv)
    revenue = round2(revenue + t.subtotal)
    vatCollected = round2(vatCollected + t.vatAmount)
  }
  const et: ExpenseTotals = inp.expenseNote
    ? expenseTotals(inp.expenseNote)
    : { reimbursementsTotal: 0, reimbursementsVat: 0, mileageKm: 0, mileageReimbursement: 0, grandTotal: 0 }
  return {
    period: inp.period,
    billableDays,
    revenue,
    expenses: et.reimbursementsTotal,
    mileageReimbursement: et.mileageReimbursement,
    vatCollected,
    vatDeductible: et.reimbursementsVat,
    profitEstimate: round2(revenue - et.reimbursementsTotal - et.mileageReimbursement),
  }
}
