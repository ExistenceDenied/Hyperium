import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import PdfPrinter from 'pdfmake'
import type { TDocumentDefinitions, Content, TableCell } from 'pdfmake/interfaces.js'
import {
  expenseTotals,
  formatEUR,
  formatKm,
  formatNumber,
  invoiceTotals,
  lineAmount,
  monthLabel,
  reimbursableKm,
  timesheetTotals,
  tripReimbursement,
  vatMention,
  vatTreatmentLabel,
} from '@af/core'
import type { Customer, DocumentGenerator, ExpenseNote, Invoice, Settings, Timesheet } from '@af/core'

// Inter — the Hyperium corporate typeface (SIL OFL), embedded into every PDF via
// pdfkit font subsetting so output is identical on every machine and in CI.
// 'Inter' bold = SemiBold (titles / headings / KPIs); 'InterMedium' = the label
// & UI weight; Inter Regular = body. Arial/sans is only a non-embedded fallback.
const FONTS = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', 'assets', 'fonts')
const printer = new PdfPrinter({
  Inter: {
    normal: resolve(FONTS, 'Inter-Regular.ttf'),
    bold: resolve(FONTS, 'Inter-SemiBold.ttf'),
    italics: resolve(FONTS, 'Inter-Italic.ttf'),
    bolditalics: resolve(FONTS, 'Inter-SemiBoldItalic.ttf'),
  },
  InterMedium: {
    normal: resolve(FONTS, 'Inter-Medium.ttf'),
    bold: resolve(FONTS, 'Inter-SemiBold.ttf'),
    italics: resolve(FONTS, 'Inter-MediumItalic.ttf'),
    bolditalics: resolve(FONTS, 'Inter-SemiBoldItalic.ttf'),
  },
})

// ---- Design tokens ----------------------------------------------------------
// Hyperium brand palette
const NAVY = '#101828' // Midnight Navy — wordmark, table headers, totals bar
const ELECTRIC = '#2563EB' // Electric Blue — the signature H-Line accent + key figures
const ZEBRA = '#F8FAFC' // Light Grey — alternating table rows
const INK = '#1A2230' // primary body text
const MUTED = '#475467' // Slate — secondary text
const HAIR = '#E2E7EF' // hairline rules
const CONTENT_W = 483 // A4 (595.28) minus 56pt margins each side

// ---- Primitives -------------------------------------------------------------
const hline = (color = HAIR, w = 0.5, top = 0, bottom = 0): Content => ({
  canvas: [{ type: 'line', x1: 0, y1: 0, x2: CONTENT_W, y2: 0, lineWidth: w, lineColor: color }],
  margin: [0, top, 0, bottom],
})

// The signature Hyperium "H-Line": a short Electric-Blue accent rule.
const hAccent = (width = 46, top = 12, bottom = 0): Content => ({
  canvas: [{ type: 'line', x1: 0, y1: 0, x2: width, y2: 0, lineWidth: 2, lineColor: ELECTRIC }],
  margin: [0, top, 0, bottom],
})

const sectionLabel = (t: string, top = 20): Content => ({
  text: t.toUpperCase(),
  font: 'InterMedium',
  color: NAVY,
  fontSize: 8.5,
  characterSpacing: 1.4,
  margin: [0, top, 0, 8],
})

const th = (text: string, align: 'left' | 'right' | 'center' = 'left'): Content => ({
  text: text.toUpperCase(),
  font: 'InterMedium',
  fontSize: 8,
  color: '#FFFFFF',
  characterSpacing: 0.6,
  alignment: align,
})

const td = (
  text: string,
  opts: { align?: 'left' | 'right' | 'center'; color?: string; bold?: boolean } = {},
): Content => ({
  text,
  fontSize: 8.5,
  color: opts.color ?? INK,
  bold: opts.bold,
  alignment: opts.align ?? 'left',
})

// House table: filled blue header (white uppercase), zebra data rows, no borders.
const tableLayout = {
  hLineWidth: () => 0,
  vLineWidth: () => 0,
  fillColor: (rowIndex: number): string | null =>
    rowIndex === 0 ? NAVY : rowIndex % 2 === 0 ? ZEBRA : null,
  paddingLeft: () => 8,
  paddingRight: () => 8,
  paddingTop: () => 6,
  paddingBottom: () => 6,
}

function masthead(s: Settings): Content[] {
  const c = s.company
  const right: Content[] = []
  if (c.email) right.push({ text: c.email, fontSize: 8, color: MUTED, alignment: 'right' })
  if (c.phone) right.push({ text: c.phone, fontSize: 8, color: MUTED, alignment: 'right' })
  if (c.iban) right.push({ text: `IBAN ${c.iban}`, fontSize: 8, color: MUTED, alignment: 'right' })
  const addr = c.addressLines.join('  ·  ')
  const head: Content = {
    columns: [
      {
        width: '*',
        stack: [
          { text: (c.name || 'Company').toUpperCase(), font: 'Inter', color: NAVY, bold: true, fontSize: 15, characterSpacing: 2.6 },
          ...(addr ? [{ text: addr, fontSize: 8, color: MUTED, margin: [0, 4, 0, 0] } as Content] : []),
          ...(c.vatNumber ? [{ text: `VAT ${c.vatNumber}`, fontSize: 8, color: MUTED, margin: [0, 1, 0, 0] } as Content] : []),
        ],
      },
      { width: 'auto', stack: right },
    ],
  }
  return [head, hAccent(46, 12, 0)]
}

function titleBlock(title: string, subtitle?: string, meta?: [string, string][]): Content {
  const metaRows: TableCell[][] = (meta ?? []).map(([l, v]): TableCell[] => [
    { text: l.toUpperCase(), font: 'InterMedium', fontSize: 7, color: MUTED, characterSpacing: 0.6, alignment: 'right', margin: [0, 0, 14, 5] },
    { text: v, fontSize: 9.5, color: INK, alignment: 'right', margin: [0, 0, 0, 5] },
  ])
  const block: Content = {
    columns: [
      {
        width: '*',
        stack: [
          { text: title, font: 'Inter', fontSize: 26, bold: true, color: NAVY, characterSpacing: 0.2 },
          ...(subtitle ? [{ text: subtitle, fontSize: 11, color: MUTED, margin: [0, 4, 0, 0] } as Content] : []),
        ],
      },
      meta
        ? { width: 'auto', table: { body: metaRows }, layout: 'noBorders' }
        : { width: 'auto', text: '' },
    ],
    margin: [0, 22, 0, 14],
  }
  return block
}

function kpiStrip(items: { label: string; value: string; sub?: string }[]): Content {
  const cells: TableCell[] = items.map(
    (it): TableCell => ({
      stack: [
        { text: it.label.toUpperCase(), font: 'InterMedium', fontSize: 7, color: MUTED, characterSpacing: 0.9 },
        { text: it.value, fontSize: 15, bold: true, color: NAVY, margin: [0, 4, 0, 0] },
        ...(it.sub ? [{ text: it.sub, fontSize: 7.5, color: MUTED, margin: [0, 2, 0, 0] } as Content] : []),
      ],
    }),
  )
  const strip: Content = {
    margin: [0, 6, 0, 0],
    table: {
      widths: items.map(() => '*'),
      body: [cells],
    },
    layout: {
      hLineWidth: (i: number, node: { table: { body: unknown[] } }) => (i === 0 || i === node.table.body.length ? 0.75 : 0),
      vLineWidth: () => 0,
      hLineColor: () => HAIR,
      paddingLeft: (i: number) => (i === 0 ? 0 : 16),
      paddingRight: () => 8,
      paddingTop: () => 11,
      paddingBottom: () => 11,
    },
  }
  return strip
}

function totalsBlock(rows: { label: string; value: string; strong?: boolean }[]): Content {
  const body: TableCell[][] = rows.map((r): TableCell[] => [
    {
      text: r.label,
      fontSize: r.strong ? 10 : 9,
      bold: r.strong,
      color: r.strong ? '#FFFFFF' : MUTED,
      characterSpacing: r.strong ? 0.5 : 0,
    },
    {
      text: r.value,
      fontSize: r.strong ? 12 : 9,
      bold: r.strong,
      color: r.strong ? '#FFFFFF' : INK,
      alignment: 'right',
    },
  ])
  const lastStrong = rows.length - 1
  const block: Content = {
    columns: [
      { width: '*', text: '' },
      {
        width: 232,
        table: { widths: ['*', 'auto'], body },
        layout: {
          // Filled blue bar on the strong (total) row, like Billit's INCL. line.
          fillColor: (i: number): string | null => (i === lastStrong ? NAVY : null),
          hLineWidth: () => 0,
          vLineWidth: () => 0,
          paddingLeft: () => 10,
          paddingRight: () => 10,
          paddingTop: (i: number) => (i === lastStrong ? 8 : 3),
          paddingBottom: (i: number) => (i === lastStrong ? 8 : 3),
        },
      },
    ],
    margin: [0, 16, 0, 0],
  }
  return block
}

function render(dd: TDocumentDefinitions): Promise<Uint8Array> {
  return new Promise((resolve, reject) => {
    const doc = printer.createPdfKitDocument(dd)
    const chunks: Buffer[] = []
    doc.on('data', (c: Buffer) => chunks.push(c))
    doc.on('end', () => resolve(new Uint8Array(Buffer.concat(chunks))))
    doc.on('error', reject)
    doc.end()
  })
}

function pageFooter(s: Settings, cp: number, pc: number): Content {
  return {
    margin: [56, 16, 56, 0],
    stack: [
      hline(HAIR, 0.5),
      {
        columns: [
          { text: (s.company.name || '').toUpperCase(), fontSize: 7, color: MUTED, characterSpacing: 0.8 },
          { text: 'PRIVATE & CONFIDENTIAL', fontSize: 7, color: MUTED, characterSpacing: 0.8, alignment: 'center' },
          { text: `${cp} / ${pc}`, fontSize: 7, color: MUTED, alignment: 'right' },
        ],
        margin: [0, 7, 0, 0],
      },
    ],
  }
}

function buildDoc(content: Content[], s: Settings): TDocumentDefinitions {
  return {
    pageSize: 'A4',
    pageMargins: [56, 56, 56, 76],
    defaultStyle: { font: 'Inter', fontSize: 9, color: INK, lineHeight: 1.32 },
    content,
    footer: (cp: number, pc: number) => pageFooter(s, cp, pc),
  }
}

// ---- Timesheet --------------------------------------------------------------
function timesheetContent(t: Timesheet, s: Settings, customers: Customer[]): Content[] {
  const tot = timesheetTotals(t)
  const custName = (id?: string) => customers.find((c) => c.id === id)?.company ?? ''
  const rows: Content[][] = [...t.days]
    .sort((a, b) => a.date.localeCompare(b.date))
    .map((d): Content[] => [
      td(d.date),
      td(d.billable ? 'Billable' : 'Non-billable', { color: d.billable ? INK : MUTED }),
      td(formatNumber(d.hours ?? 8, 1), { align: 'right' }),
      td(custName(d.customerId)),
      td(d.project ?? ''),
      td(d.comment ?? '', { color: MUTED }),
    ])
  return [
    ...masthead(s),
    titleBlock('Timesheet', monthLabel(t.period)),
    kpiStrip([
      { label: 'Billable days', value: String(tot.billableDays), sub: `${formatNumber(tot.billableHours, 1)} h` },
      { label: 'Non-billable', value: String(tot.nonBillableDays), sub: `${formatNumber(tot.nonBillableHours, 1)} h` },
      { label: 'Days worked', value: String(tot.totalWorkedDays) },
      { label: 'Total hours', value: formatNumber(tot.totalHours, 1) },
    ]),
    sectionLabel('Daily register'),
    t.days.length
      ? {
          table: {
            headerRows: 1,
            widths: [56, 62, 34, '*', '*', '*'],
            body: [[th('Date'), th('Type'), th('Hours', 'right'), th('Customer'), th('Project'), th('Comment')], ...rows],
          },
          layout: tableLayout,
        }
      : { text: 'No days registered.', color: MUTED, italics: true, fontSize: 9 },
    ...(t.note ? [sectionLabel('Notes'), { text: t.note, fontSize: 9, color: INK } as Content] : []),
  ]
}

// ---- Invoice ----------------------------------------------------------------
function invoiceContent(inv: Invoice, s: Settings, customers: Customer[]): Content[] {
  const cust = customers.find((c) => c.id === inv.customerId)
  const tot = invoiceTotals(inv)
  const mention = vatMention[inv.vatTreatment]
  const meta: [string, string][] = [
    ['Invoice no.', inv.number],
    ['Issue date', inv.date],
    ['Due date', inv.dueDate],
  ]
  if (inv.reference && inv.reference.length) meta.push(['Your reference', inv.reference])

  const lineRows: Content[][] = inv.lines.map((l): Content[] => [
    td(l.description),
    td(formatNumber(l.quantity), { align: 'right' }),
    td(l.unit),
    td(formatEUR(l.unitPrice), { align: 'right' }),
    td(formatEUR(lineAmount(l)), { align: 'right', bold: true }),
  ])

  return [
    ...masthead(s),
    titleBlock('Invoice', undefined, meta),
    sectionLabel('Billed to', 6),
    {
      stack: [
        { text: cust?.company ?? '', fontSize: 10, bold: true, color: INK },
        ...(cust?.contactPerson ? [{ text: cust.contactPerson, fontSize: 8.5, color: MUTED, margin: [0, 1, 0, 0] } as Content] : []),
        ...(cust?.addressLines?.length ? [{ text: cust.addressLines.join(', '), fontSize: 8.5, color: MUTED, margin: [0, 1, 0, 0] } as Content] : []),
        ...(cust?.vatNumber ? [{ text: `VAT ${cust.vatNumber}`, fontSize: 8.5, color: MUTED, margin: [0, 1, 0, 0] } as Content] : []),
        { text: vatTreatmentLabel[inv.vatTreatment], fontSize: 8, color: MUTED, margin: [0, 4, 0, 0], italics: true },
      ],
    },
    sectionLabel('Services'),
    {
      table: {
        headerRows: 1,
        widths: ['*', 40, 40, 68, 72],
        body: [
          [th('Description'), th('Qty', 'right'), th('Unit'), th('Unit price', 'right'), th('Amount', 'right')],
          ...lineRows,
        ],
      },
      layout: tableLayout,
    },
    totalsBlock([
      { label: 'Subtotal', value: formatEUR(tot.subtotal) },
      { label: `VAT ${formatNumber(tot.vatRatePct)}%`, value: formatEUR(tot.vatAmount) },
      { label: 'Total due', value: formatEUR(tot.total), strong: true },
    ]),
    ...(mention ? [{ text: mention, fontSize: 7.5, color: MUTED, italics: true, margin: [0, 14, 0, 0] } as Content] : []),
    sectionLabel('Payment'),
    {
      columns: [
        {
          width: '*',
          stack: [
            { text: `IBAN  ${s.company.iban || '—'}${s.company.bic ? `      BIC  ${s.company.bic}` : ''}`, fontSize: 9, color: INK },
            { text: `Structured reference  ${inv.structuredReference}`, fontSize: 9, bold: true, color: ELECTRIC, margin: [0, 4, 0, 0] },
            { text: `Please pay by ${inv.dueDate}.`, fontSize: 8, color: MUTED, margin: [0, 4, 0, 0] },
          ],
        },
      ],
    },
    ...(inv.notes ? [{ text: inv.notes, fontSize: 8, color: MUTED, margin: [0, 12, 0, 0] } as Content] : []),
  ]
}

// ---- Expense note -----------------------------------------------------------
function expenseContent(e: ExpenseNote, s: Settings, customers: Customer[]): Content[] {
  const tot = expenseTotals(e)
  const custName = (id?: string) => customers.find((c) => c.id === id)?.company ?? ''
  const content: Content[] = [
    ...masthead(s),
    titleBlock('Expense note', monthLabel(e.period)),
    kpiStrip([
      { label: 'Reimbursements', value: formatEUR(tot.reimbursementsTotal) },
      { label: 'Mileage', value: formatKm(tot.mileageKm), sub: formatEUR(tot.mileageReimbursement) },
      { label: 'VAT deductible', value: formatEUR(tot.reimbursementsVat) },
      { label: 'Total', value: formatEUR(tot.grandTotal) },
    ]),
    sectionLabel('Reimbursements'),
  ]

  if (e.items.length) {
    content.push({
      table: {
        headerRows: 1,
        widths: [58, '*', '*', 60, 50],
        body: [
          [th('Date'), th('Category'), th('Description'), th('Amount', 'right'), th('VAT', 'right')],
          ...e.items.map((i): Content[] => [
            td(i.date),
            td(i.category),
            td(`${i.description}${i.supplier ? ` — ${i.supplier}` : ''}`),
            td(formatEUR(i.amount), { align: 'right' }),
            td(formatEUR(i.vatAmount ?? 0), { align: 'right', color: MUTED }),
          ]),
        ],
      },
      layout: tableLayout,
    })
  } else {
    content.push({ text: 'No reimbursements.', color: MUTED, italics: true, fontSize: 9 })
  }

  content.push(sectionLabel(`Mileage — ${formatNumber(e.mileageRatePerKm)} €/km`))
  if (e.trips.length) {
    content.push({
      table: {
        headerRows: 1,
        widths: ['*', '*', '*', 30, 42, 54],
        body: [
          [th('Date'), th('From → To'), th('Purpose / client'), th('RT', 'center'), th('Km', 'right'), th('Amount', 'right')],
          ...e.trips.map((t): Content[] => [
            td(t.date),
            td(`${t.departure} → ${t.destination}`),
            td(`${t.purpose}${t.customerId ? ` (${custName(t.customerId)})` : ''}`, { color: MUTED }),
            td(t.roundTrip ? '×2' : '—', { align: 'center', color: MUTED }),
            td(formatKm(reimbursableKm(t)), { align: 'right' }),
            td(formatEUR(tripReimbursement(t, e.mileageRatePerKm)), { align: 'right' }),
          ]),
        ],
      },
      layout: tableLayout,
    })
  } else {
    content.push({ text: 'No trips.', color: MUTED, italics: true, fontSize: 9 })
  }

  content.push(
    totalsBlock([
      { label: 'Reimbursements', value: formatEUR(tot.reimbursementsTotal) },
      { label: `Mileage (${formatKm(tot.mileageKm)})`, value: formatEUR(tot.mileageReimbursement) },
      { label: 'Total', value: formatEUR(tot.grandTotal), strong: true },
    ]),
  )
  return content
}

export const pdfGenerator: DocumentGenerator = {
  format: 'pdf',
  timesheet: (t, s, customers) => render(buildDoc(timesheetContent(t, s, customers), s)),
  invoice: (i, s, customers) => render(buildDoc(invoiceContent(i, s, customers), s)),
  expense: (e, s, customers) => render(buildDoc(expenseContent(e, s, customers), s)),
}
