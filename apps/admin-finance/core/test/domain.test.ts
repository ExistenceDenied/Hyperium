import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  round2,
  round4,
  sum,
  computeVat,
  reimbursableKm,
  tripReimbursement,
  mileageTotals,
  structuredReference,
  referenceSeedFromInvoice,
  periodKey,
  parsePeriodKey,
  addDaysISO,
  monthDays,
  isWeekend,
  isoWeekday,
  currentPeriod,
  timesheetTotals,
  invoiceTotals,
  lineAmount,
  formatInvoiceNumber,
  buildInvoice,
  expenseTotals,
  monthlyDashboard,
  parseCoda,
  reconcile,
  ublInvoice,
  type Company,
  type Customer,
  type Timesheet,
  type ExpenseNote,
  type Invoice,
} from '@af/core'

// ---- money ------------------------------------------------------------------
test('round2 rounds to two decimals and kills float noise', () => {
  assert.equal(round2(0.1 + 0.2), 0.3)
  assert.equal(round2(1.005), 1.01) // EPSILON nudge — the classic 1.005 case
  assert.equal(round2(2.675), 2.68)
  assert.equal(round2(950 * 3), 2850)
})
test('round4 keeps four decimals for rates', () => {
  assert.equal(round4(0.44151234), 0.4415)
})
test('sum rounds the total', () => {
  assert.equal(sum([0.1, 0.2, 0.3]), 0.6)
  assert.equal(sum([]), 0)
  assert.equal(sum([1000, 250.5, 0.5]), 1251)
})

// ---- VAT --------------------------------------------------------------------
test('computeVat applies the standard rate only for the standard treatment', () => {
  assert.deepEqual(computeVat(1000, 'standard', 21), { ratePct: 21, amount: 210 })
  assert.deepEqual(computeVat(1000, 'reverse_charge_eu', 21), { ratePct: 0, amount: 0 })
  assert.deepEqual(computeVat(1000, 'exempt', 21), { ratePct: 0, amount: 0 })
  assert.deepEqual(computeVat(1000, 'zero', 21), { ratePct: 0, amount: 0 })
})
test('computeVat rounds the VAT amount', () => {
  assert.equal(computeVat(99.99, 'standard', 21).amount, 21) // 20.9979 -> 21.00
})

// ---- mileage ----------------------------------------------------------------
test('reimbursableKm doubles round trips', () => {
  assert.equal(reimbursableKm({ distanceKm: 45, roundTrip: true }), 90)
  assert.equal(reimbursableKm({ distanceKm: 60, roundTrip: false }), 60)
})
test('tripReimbursement and mileageTotals use the official rate', () => {
  assert.equal(tripReimbursement({ distanceKm: 45, roundTrip: true }, 0.4415), 39.74)
  const totals = mileageTotals(
    [
      { distanceKm: 45, roundTrip: true }, // 90
      { distanceKm: 60, roundTrip: false }, // 60
    ],
    0.4415,
  )
  assert.equal(totals.totalKm, 150)
  assert.equal(totals.totalReimbursement, 66.22) // round2(150 * 0.4415) — float lands on 66.2249…
})

// ---- structured reference (Belgian mod-97) ----------------------------------
test('structuredReference computes the mod-97 check digits', () => {
  // Matches the real seeded invoices 2026-001 / 2026-002.
  assert.equal(structuredReference(referenceSeedFromInvoice(2026, 1)), '+++020/2600/00178+++')
  assert.equal(structuredReference(referenceSeedFromInvoice(2026, 2)), '+++020/2600/00279+++')
})
test('structuredReference maps a zero remainder to 97', () => {
  // base 0000000097 -> 97 % 97 = 0 -> becomes 97
  assert.equal(structuredReference(97), '+++000/0000/09797+++')
})
test('referenceSeedFromInvoice is stable', () => {
  assert.equal(referenceSeedFromInvoice(2026, 7), 202600007)
})

// ---- period -----------------------------------------------------------------
test('periodKey / parsePeriodKey round-trip', () => {
  assert.equal(periodKey({ year: 2026, month: 7 }), '2026-07')
  assert.deepEqual(parsePeriodKey('2026-07'), { year: 2026, month: 7 })
})
test('addDaysISO adds calendar days across month boundaries', () => {
  assert.equal(addDaysISO('2026-07-31', 30), '2026-08-30')
  assert.equal(addDaysISO('2026-07-31', 45), '2026-09-14') // matches invoice 2026-002 due date
})
test('monthDays counts days including the leap-year February', () => {
  assert.equal(monthDays({ year: 2026, month: 2 }).length, 28)
  assert.equal(monthDays({ year: 2024, month: 2 }).length, 29)
  assert.equal(monthDays({ year: 2026, month: 7 }).length, 31)
})
test('isWeekend and isoWeekday classify days', () => {
  assert.equal(isWeekend(new Date(2026, 6, 4)), true) // 2026-07-04 is a Saturday
  assert.equal(isWeekend(new Date(2026, 6, 6)), false) // Monday
  assert.equal(isoWeekday(new Date(2026, 6, 5)), 7) // Sunday -> 7
  assert.equal(isoWeekday(new Date(2026, 6, 6)), 1) // Monday -> 1
})
test('currentPeriod reads a Date', () => {
  assert.deepEqual(currentPeriod(new Date(2026, 6, 15)), { year: 2026, month: 7 })
})

// ---- calculators ------------------------------------------------------------
const mkTimesheet = (): Timesheet => ({
  id: 'ts1',
  period: { year: 2026, month: 7 },
  days: [
    { date: '2026-07-01', billable: true, hours: 8, customerId: 'c1' },
    { date: '2026-07-02', billable: true, hours: 8, customerId: 'c1' },
    { date: '2026-07-03', billable: true, hours: 6, customerId: 'c1' },
    { date: '2026-07-04', billable: false, hours: 4 },
  ],
  status: 'draft',
  comments: [],
  createdAt: '2026-07-01T00:00:00Z',
  updatedAt: '2026-07-01T00:00:00Z',
})

test('timesheetTotals splits billable vs non-billable days and hours', () => {
  const t = timesheetTotals(mkTimesheet())
  assert.equal(t.totalWorkedDays, 4)
  assert.equal(t.billableDays, 3)
  assert.equal(t.nonBillableDays, 1)
  assert.equal(t.billableHours, 22)
  assert.equal(t.nonBillableHours, 4)
  assert.equal(t.totalHours, 26)
})

test('lineAmount and invoiceTotals compute subtotal, VAT and total', () => {
  assert.equal(lineAmount({ description: 'x', quantity: 3, unit: 'day', unitPrice: 950 }), 2850)
  const totals = invoiceTotals({
    lines: [
      { description: 'a', quantity: 3, unit: 'day', unitPrice: 950 },
      { description: 'b', quantity: 2, unit: 'hour', unitPrice: 125 },
    ],
    vatTreatment: 'standard',
    standardVatRatePct: 21,
  })
  assert.equal(totals.subtotal, 3100)
  assert.equal(totals.vatRatePct, 21)
  assert.equal(totals.vatAmount, 651)
  assert.equal(totals.total, 3751)
})
test('invoiceTotals charges no VAT under reverse charge', () => {
  const totals = invoiceTotals({
    lines: [{ description: 'a', quantity: 1, unit: 'day', unitPrice: 1000 }],
    vatTreatment: 'reverse_charge_eu',
    standardVatRatePct: 21,
  })
  assert.equal(totals.vatAmount, 0)
  assert.equal(totals.total, 1000)
})

test('formatInvoiceNumber expands the tokens', () => {
  assert.equal(formatInvoiceNumber('{year}-{seq:3}', 2026, 7), '2026-007')
  assert.equal(formatInvoiceNumber('{year}-{seq}', 2026, 7), '2026-7')
  assert.equal(formatInvoiceNumber('INV{seq:5}', 2026, 42), 'INV00042')
})

const company: Company = {
  name: 'Hyperium BV',
  legalForm: 'BV',
  vatNumber: 'BE0123.456.789',
  addressLines: [],
  iban: '',
  bic: '',
  email: '',
  phone: '',
  invoiceNumberFormat: '{year}-{seq:3}',
  nextInvoiceSeq: 1,
}
const customer: Customer = {
  id: 'c1',
  company: 'Client NV',
  contactPerson: '',
  addressLines: [],
  vatNumber: '',
  email: '',
  defaultDayRate: 950,
  defaultHourlyRate: 125,
  paymentTermsDays: 30,
  vatTreatment: 'standard',
}

test('buildInvoice bills a timesheet by day', () => {
  const inv = buildInvoice({
    id: 'i1',
    year: 2026,
    seq: 5,
    date: '2026-07-31',
    company,
    customer,
    timesheet: mkTimesheet(),
    basis: 'day',
    standardVatRatePct: 21,
    createdAt: '2026-07-31T00:00:00Z',
  })
  assert.equal(inv.number, '2026-005')
  assert.equal(inv.dueDate, '2026-08-30') // date + 30 day terms
  assert.equal(inv.lines.length, 1)
  assert.equal(inv.lines[0]!.quantity, 3) // 3 billable days
  assert.equal(inv.lines[0]!.unitPrice, 950)
  assert.equal(inv.vatTreatment, 'standard')
  assert.match(inv.structuredReference, /^\+\+\+\d{3}\/\d{4}\/\d{5}\+\+\+$/)
})
test('buildInvoice bills a timesheet by hour and appends extra lines', () => {
  const inv = buildInvoice({
    id: 'i2',
    year: 2026,
    seq: 6,
    date: '2026-07-31',
    company,
    customer,
    timesheet: mkTimesheet(),
    basis: 'hour',
    extraLines: [{ description: 'Travel', quantity: 1, unit: 'item', unitPrice: 40 }],
    standardVatRatePct: 21,
    createdAt: '2026-07-31T00:00:00Z',
  })
  assert.equal(inv.lines.length, 2)
  assert.equal(inv.lines[0]!.quantity, 22) // 22 billable hours
  assert.equal(inv.lines[0]!.unitPrice, 125)
  assert.equal(inv.lines[1]!.description, 'Travel')
})

const mkExpense = (): ExpenseNote => ({
  id: 'e1',
  period: { year: 2026, month: 7 },
  items: [
    { id: 'x1', date: '2026-07-05', category: 'Software', description: '', supplier: '', amount: 289, vatAmount: 50.15, status: 'submitted' },
  ],
  trips: [
    { id: 't1', date: '2026-07-01', departure: '', destination: '', purpose: '', distanceKm: 45, roundTrip: true },
    { id: 't2', date: '2026-07-03', departure: '', destination: '', purpose: '', distanceKm: 60, roundTrip: false },
  ],
  mileageRatePerKm: 0.4415,
  status: 'draft',
  comments: [],
  createdAt: '2026-07-01T00:00:00Z',
  updatedAt: '2026-07-01T00:00:00Z',
})

test('expenseTotals sums reimbursements, VAT and mileage', () => {
  const t = expenseTotals(mkExpense())
  assert.equal(t.reimbursementsTotal, 289)
  assert.equal(t.reimbursementsVat, 50.15)
  assert.equal(t.mileageKm, 150)
  assert.equal(t.mileageReimbursement, 66.22)
  assert.equal(t.grandTotal, 355.22) // 289 + 66.22
})

test('monthlyDashboard aggregates revenue, VAT and a profit estimate', () => {
  const inv = buildInvoice({
    id: 'i1',
    year: 2026,
    seq: 1,
    date: '2026-07-31',
    company,
    customer,
    timesheet: mkTimesheet(),
    basis: 'day',
    standardVatRatePct: 21,
    createdAt: '2026-07-31T00:00:00Z',
  })
  const d = monthlyDashboard({
    period: { year: 2026, month: 7 },
    timesheet: mkTimesheet(),
    invoices: [inv],
    expenseNote: mkExpense(),
  })
  assert.equal(d.billableDays, 3)
  assert.equal(d.revenue, 2850) // 3 * 950, ex VAT
  assert.equal(d.vatCollected, 598.5) // 21% of 2850
  assert.equal(d.expenses, 289)
  assert.equal(d.mileageReimbursement, 66.22)
  assert.equal(d.profitEstimate, 2494.78) // round2(2850 - 289 - 66.22)
})

// ---- CODA reconciliation ----------------------------------------------------
const codaLine = (o: { sign: 'credit' | 'debit'; amount: number; date: string; ref?: string; free?: string }): string => {
  const amt = String(Math.round(o.amount * 1000)).padStart(15, '0')
  const comm = (o.ref ? '101' + o.ref : (o.free ?? '')).padEnd(53, ' ')
  const head = '21' + '0000' + '0000' + ' '.repeat(21) // 31 chars, idx 0..30
  return (head + (o.sign === 'debit' ? '1' : '0') + amt + o.date + '00000000' + (o.ref ? '1' : '0') + comm).padEnd(128, ' ')
}

test('parseCoda extracts sign, amount, value date and the structured reference', () => {
  const [m] = parseCoda(codaLine({ sign: 'credit', amount: 3448.5, date: '150826', ref: '020260000178' }))
  assert.equal(m!.sign, 'credit')
  assert.equal(m!.amount, 3448.5)
  assert.equal(m!.valueDate, '2026-08-15')
  assert.equal(m!.structuredRef, '020260000178')
  const [d] = parseCoda(codaLine({ sign: 'debit', amount: 12.5, date: '010126', free: 'COFFEE' }))
  assert.equal(d!.sign, 'debit')
  assert.equal(d!.structuredRef, undefined)
})

test('reconcile matches income by structured reference and flags the rest', () => {
  const inv: Invoice = buildInvoice({
    id: 'ri',
    year: 2026,
    seq: 1,
    date: '2026-08-15',
    company,
    customer,
    extraLines: [{ description: 'Advisory', quantity: 1, unit: 'day', unitPrice: 2850 }],
    standardVatRatePct: 21,
    createdAt: '2026-08-15T00:00:00Z',
  })
  const ref = inv.structuredReference.replace(/\D/g, '')
  const expense = mkExpense() // one item: 289 + 50.15 VAT = 339.15 gross

  const coda = [
    codaLine({ sign: 'credit', amount: invoiceTotals(inv).total, date: '200826', ref }), // pays the invoice
    codaLine({ sign: 'credit', amount: 500, date: '210826', free: 'GIFT' }), // income, no invoice
    codaLine({ sign: 'debit', amount: 339.15, date: '050826', free: 'ACME' }), // matches an expense
    codaLine({ sign: 'debit', amount: 999.99, date: '060826', free: 'MYSTERY' }), // spend, no receipt
  ].join('\r\n')

  const r = reconcile(parseCoda(coda), [inv], [expense])
  assert.equal(r.totals.invoicesPaid, 1)
  assert.equal(r.paidInvoices[0]!.number, inv.number)
  assert.equal(r.paidInvoices[0]!.amountMatches, true)
  assert.equal(r.unpaidInvoices.length, 0)
  assert.equal(r.unexplainedCredits.length, 1)
  assert.equal(r.unexplainedCredits[0]!.amount, 500)
  assert.equal(r.totals.debitsMatched, 1)
  assert.equal(r.unexplainedDebits.length, 1)
  assert.equal(r.unexplainedDebits[0]!.amount, 999.99)
  assert.equal(r.totals.credits, 3948.5) // 3448.5 + 500
  assert.equal(r.totals.debits, 1339.14) // 339.15 + 999.99
})

// ---- UBL (Peppol) e-invoice -------------------------------------------------
test('ublInvoice renders a Peppol-shaped UBL invoice with the right totals', () => {
  const inv: Invoice = buildInvoice({
    id: 'u1',
    year: 2026,
    seq: 7,
    date: '2026-07-31',
    company,
    customer,
    extraLines: [{ description: 'Consulting', quantity: 1, unit: 'day', unitPrice: 2850 }],
    standardVatRatePct: 21,
    createdAt: '2026-07-31T00:00:00Z',
  })
  const xml = ublInvoice(inv, customer, company)
  assert.ok(xml.startsWith('<?xml'))
  assert.match(xml, /<Invoice[\s>]/)
  assert.ok(xml.includes('urn:cen.eu:en16931')) // Peppol BIS 3.0 customization
  assert.ok(xml.includes(`<cbc:ID>${inv.number}</cbc:ID>`))
  assert.ok(xml.includes('<cbc:IssueDate>2026-07-31</cbc:IssueDate>'))
  assert.ok(xml.includes('<cbc:Percent>21</cbc:Percent>'))
  assert.ok(xml.includes('<cbc:TaxInclusiveAmount currencyID="EUR">3448.50</cbc:TaxInclusiveAmount>'))
  assert.ok(xml.includes('<cbc:PayableAmount currencyID="EUR">3448.50</cbc:PayableAmount>'))
  assert.ok(xml.includes(`<cbc:PaymentID>${inv.structuredReference}</cbc:PaymentID>`))
  assert.ok(xml.includes('<cac:InvoiceLine>'))
})
