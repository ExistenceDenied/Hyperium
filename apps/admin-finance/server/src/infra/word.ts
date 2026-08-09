import {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  Packer,
  PageNumber,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
  VerticalAlign,
  WidthType,
} from 'docx'
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
import { embedFonts } from './embedFonts.js'

// ---- Design tokens (Hyperium brand) -----------------------------------------
const NAVY = '101828' // Midnight Navy
const ELECTRIC = '2563EB' // Electric Blue accent
const INK = '1A2230'
const MUTED = '475467' // Slate
const HAIR = 'E2E7EF'

const NO = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' }
const HAIRLINE = { style: BorderStyle.SINGLE, size: 4, color: HAIR }
const NAVYLINE = { style: BorderStyle.SINGLE, size: 10, color: NAVY }
const NO_BORDERS = { top: NO, bottom: NO, left: NO, right: NO, insideHorizontal: NO, insideVertical: NO }

// Inter — the Hyperium corporate typeface (SIL OFL), embedded into every .docx
// (see embedFonts) so it renders identically without the fonts installed; Arial
// is only a non-embedded fallback. 'Inter' bold = SemiBold (titles/headings);
// 'Inter Medium' is the label/UI weight.
const SANS = 'Inter'
const MEDIUM = 'Inter Medium'

// ---- Text primitives (sizes are half-points) --------------------------------
const t = (
  text: string,
  o: { size?: number; bold?: boolean; color?: string; caps?: boolean; italics?: boolean; font?: string } = {},
) =>
  new TextRun({
    text,
    size: o.size ?? 18,
    bold: o.bold,
    color: o.color ?? INK,
    allCaps: o.caps,
    italics: o.italics,
    font: o.font ?? SANS,
  })

const muted = (text: string, size = 16) => new Paragraph({ children: [t(text, { color: MUTED, size })] })

const sectionLabel = (text: string) =>
  new Paragraph({
    spacing: { before: 320, after: 120 },
    children: [t(text, { caps: true, color: NAVY, size: 17, font: MEDIUM })],
  })

const spacer = (h = 120) => new Paragraph({ spacing: { after: h }, children: [] })

// Full-width navy rule (a paragraph with a bottom border).
const navyRule = () =>
  new Paragraph({ border: { bottom: { style: BorderStyle.SINGLE, size: 10, color: NAVY } }, spacing: { after: 40 }, children: [] })

// ---- Cells & tables ---------------------------------------------------------
function tc(
  children: Paragraph[],
  o: { width?: number; borders?: object; align?: (typeof VerticalAlign)[keyof typeof VerticalAlign] } = {},
): TableCell {
  return new TableCell({
    children,
    verticalAlign: o.align ?? VerticalAlign.CENTER,
    margins: { top: 70, bottom: 70, left: 0, right: 140 },
    ...(o.width ? { width: { size: o.width, type: WidthType.PERCENTAGE } } : {}),
    borders: { top: NO, bottom: NO, left: NO, right: NO, ...(o.borders ?? {}) },
  })
}

const cellText = (text: string, o: { right?: boolean; bold?: boolean; color?: string } = {}) =>
  new Paragraph({
    alignment: o.right ? AlignmentType.RIGHT : AlignmentType.LEFT,
    children: [t(text, { size: 17, bold: o.bold, color: o.color ?? INK })],
  })

const cellHead = (text: string, right?: boolean) =>
  new Paragraph({
    alignment: right ? AlignmentType.RIGHT : AlignmentType.LEFT,
    children: [t(text, { caps: true, color: MUTED, size: 13, font: MEDIUM })],
  })

interface Col {
  h: string
  w: number
  right?: boolean
}
function dataTable(cols: Col[], rows: (string | { text: string; muted?: boolean; bold?: boolean })[][]): Table {
  const header = new TableRow({
    tableHeader: true,
    children: cols.map((c) => tc([cellHead(c.h, c.right)], { width: c.w, borders: { bottom: NAVYLINE } })),
  })
  const body = rows.map(
    (r) =>
      new TableRow({
        children: r.map((val, i) => {
          const cell = typeof val === 'string' ? { text: val } : val
          return tc([cellText(cell.text, { right: cols[i].right, bold: cell.bold, color: cell.muted ? MUTED : INK })], {
            width: cols[i].w,
            borders: { bottom: HAIRLINE },
          })
        }),
      }),
  )
  return new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, borders: NO_BORDERS, rows: [header, ...body] })
}

function masthead(s: Settings): (Paragraph | Table)[] {
  const c = s.company
  const rightLines = [c.email, c.phone, c.iban ? `IBAN ${c.iban}` : ''].filter(Boolean)
  const table = new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: NO_BORDERS,
    rows: [
      new TableRow({
        children: [
          tc(
            [
              new Paragraph({ children: [t(c.name || 'Company', { bold: true, color: NAVY, size: 30, caps: true })] }),
              ...(c.addressLines.length ? [muted(c.addressLines.join('  ·  '))] : []),
              ...(c.vatNumber ? [muted(`VAT ${c.vatNumber}`)] : []),
            ],
            { width: 60 },
          ),
          tc(
            rightLines.map((l) => new Paragraph({ alignment: AlignmentType.RIGHT, children: [t(l, { color: MUTED, size: 16 })] })),
            { width: 40, align: VerticalAlign.TOP },
          ),
        ],
      }),
    ],
  })
  return [table, navyRule(), spacer(80)]
}

function titleBlock(title: string, subtitle?: string): Paragraph[] {
  return [
    new Paragraph({ spacing: { before: 160, after: subtitle ? 20 : 120 }, children: [t(title, { bold: true, color: NAVY, size: 48 })] }),
    ...(subtitle ? [new Paragraph({ spacing: { after: 120 }, children: [t(subtitle, { color: MUTED, size: 22 })] })] : []),
  ]
}

function kpiBand(items: { label: string; value: string; sub?: string }[]): Table {
  const w = Math.floor(100 / items.length)
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: { ...NO_BORDERS, top: HAIRLINE, bottom: HAIRLINE },
    rows: [
      new TableRow({
        children: items.map((it) =>
          new TableCell({
            width: { size: w, type: WidthType.PERCENTAGE },
            margins: { top: 160, bottom: 160, left: 0, right: 120 },
            borders: { top: NO, bottom: NO, left: NO, right: NO },
            children: [
              new Paragraph({ children: [t(it.label.toUpperCase(), { caps: true, color: MUTED, size: 13 })] }),
              new Paragraph({ spacing: { before: 40 }, children: [t(it.value, { bold: true, color: NAVY, size: 30 })] }),
              ...(it.sub ? [new Paragraph({ spacing: { before: 20 }, children: [t(it.sub, { color: MUTED, size: 15 })] })] : []),
            ],
          }),
        ),
      }),
    ],
  })
}

function totalsBlock(rows: { label: string; value: string; strong?: boolean }[]): Table {
  return new Table({
    alignment: AlignmentType.RIGHT,
    width: { size: 46, type: WidthType.PERCENTAGE },
    borders: NO_BORDERS,
    rows: rows.map(
      (r) =>
        new TableRow({
          children: [
            tc([new Paragraph({ children: [t(r.label, { color: r.strong ? NAVY : MUTED, bold: r.strong, size: r.strong ? 20 : 17 })] })], {
              width: 55,
              borders: r.strong ? { top: NAVYLINE } : {},
            }),
            tc(
              [
                new Paragraph({
                  alignment: AlignmentType.RIGHT,
                  children: [t(r.value, { color: r.strong ? NAVY : INK, bold: r.strong, size: r.strong ? 26 : 17 })],
                }),
              ],
              { width: 45, borders: r.strong ? { top: NAVYLINE } : {} },
            ),
          ],
        }),
    ),
  })
}

function footer(s: Settings): Footer {
  const cellP = (text: string, align: (typeof AlignmentType)[keyof typeof AlignmentType], children?: (string | TextRun)[]) =>
    new Paragraph({
      alignment: align,
      children: children ? children.map((c) => (typeof c === 'string' ? t(c, { color: MUTED, size: 13 }) : c)) : [t(text, { caps: true, color: MUTED, size: 13 })],
    })
  return new Footer({
    children: [
      new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        borders: { ...NO_BORDERS, top: HAIRLINE },
        rows: [
          new TableRow({
            children: [
              tc([cellP((s.company.name || '').toUpperCase(), AlignmentType.LEFT)], { width: 33, borders: { top: HAIRLINE } }),
              tc([cellP('PRIVATE & CONFIDENTIAL', AlignmentType.CENTER)], { width: 34, borders: { top: HAIRLINE } }),
              tc(
                [
                  cellP('', AlignmentType.RIGHT, [
                    new TextRun({ children: [PageNumber.CURRENT], color: MUTED, size: 13 }),
                    t(' / ', { color: MUTED, size: 13 }),
                    new TextRun({ children: [PageNumber.TOTAL_PAGES], color: MUTED, size: 13 }),
                  ]),
                ],
                { width: 33, borders: { top: HAIRLINE } },
              ),
            ],
          }),
        ],
      }),
    ],
  })
}

function pack(children: (Paragraph | Table)[], s: Settings): Promise<Uint8Array> {
  const doc = new Document({
    styles: { default: { document: { run: { font: SANS, size: 18, color: INK } } } },
    sections: [
      {
        properties: { page: { margin: { top: 1080, bottom: 1080, left: 1120, right: 1120 } } },
        footers: { default: footer(s) },
        children,
      },
    ],
  })
  return Packer.toBuffer(doc).then((b) => embedFonts(new Uint8Array(b)))
}

// ---- Timesheet --------------------------------------------------------------
function timesheetChildren(t2: Timesheet, s: Settings, customers: Customer[]): (Paragraph | Table)[] {
  const tot = timesheetTotals(t2)
  const custName = (id?: string) => customers.find((c) => c.id === id)?.company ?? ''
  return [
    ...masthead(s),
    ...titleBlock('Timesheet', monthLabel(t2.period)),
    kpiBand([
      { label: 'Billable days', value: String(tot.billableDays), sub: `${formatNumber(tot.billableHours, 1)} h` },
      { label: 'Non-billable', value: String(tot.nonBillableDays), sub: `${formatNumber(tot.nonBillableHours, 1)} h` },
      { label: 'Days worked', value: String(tot.totalWorkedDays) },
      { label: 'Total hours', value: formatNumber(tot.totalHours, 1) },
    ]),
    sectionLabel('Daily register'),
    dataTable(
      [
        { h: 'Date', w: 13 },
        { h: 'Type', w: 14 },
        { h: 'Hours', w: 8, right: true },
        { h: 'Customer', w: 22 },
        { h: 'Project', w: 22 },
        { h: 'Comment', w: 21 },
      ],
      [...t2.days]
        .sort((a, b) => a.date.localeCompare(b.date))
        .map((d) => [
          d.date,
          { text: d.billable ? 'Billable' : 'Non-billable', muted: !d.billable },
          formatNumber(d.hours ?? 8, 1),
          custName(d.customerId),
          d.project ?? '',
          { text: d.comment ?? '', muted: true },
        ]),
    ),
    ...(t2.note ? [sectionLabel('Notes'), muted(t2.note, 18)] : []),
  ]
}

// ---- Invoice ----------------------------------------------------------------
function invoiceChildren(inv: Invoice, s: Settings, customers: Customer[]): (Paragraph | Table)[] {
  const cust = customers.find((c) => c.id === inv.customerId)
  const tot = invoiceTotals(inv)
  const mention = vatMention[inv.vatTreatment]
  const metaLine = `Invoice no. ${inv.number}    ·    Issue ${inv.date}    ·    Due ${inv.dueDate}${inv.reference ? `    ·    Ref ${inv.reference}` : ''}`
  return [
    ...masthead(s),
    ...titleBlock('Invoice'),
    muted(metaLine, 17),
    sectionLabel('Billed to'),
    new Paragraph({ children: [t(cust?.company ?? '', { bold: true, size: 20 })] }),
    ...(cust?.contactPerson ? [muted(cust.contactPerson)] : []),
    ...(cust?.addressLines?.length ? [muted(cust.addressLines.join(', '))] : []),
    ...(cust?.vatNumber ? [muted(`VAT ${cust.vatNumber}`)] : []),
    new Paragraph({ spacing: { before: 40 }, children: [t(vatTreatmentLabel[inv.vatTreatment], { italics: true, color: MUTED, size: 15 })] }),
    sectionLabel('Services'),
    dataTable(
      [
        { h: 'Description', w: 46 },
        { h: 'Qty', w: 10, right: true },
        { h: 'Unit', w: 10 },
        { h: 'Unit price', w: 16, right: true },
        { h: 'Amount', w: 18, right: true },
      ],
      inv.lines.map((l) => [
        l.description,
        formatNumber(l.quantity),
        l.unit,
        formatEUR(l.unitPrice),
        { text: formatEUR(lineAmount(l)), bold: true },
      ]),
    ),
    spacer(80),
    totalsBlock([
      { label: 'Subtotal', value: formatEUR(tot.subtotal) },
      { label: `VAT ${formatNumber(tot.vatRatePct)}%`, value: formatEUR(tot.vatAmount) },
      { label: 'Total due', value: formatEUR(tot.total), strong: true },
    ]),
    ...(mention ? [new Paragraph({ spacing: { before: 200 }, children: [t(mention, { italics: true, color: MUTED, size: 15 })] })] : []),
    sectionLabel('Payment'),
    new Paragraph({ children: [t(`IBAN  ${s.company.iban || '—'}${s.company.bic ? `      BIC  ${s.company.bic}` : ''}`, { size: 18 })] }),
    new Paragraph({ spacing: { before: 40 }, children: [t(`Structured reference  ${inv.structuredReference}`, { bold: true, color: ELECTRIC, size: 18 })] }),
    new Paragraph({ spacing: { before: 40 }, children: [t(`Please pay by ${inv.dueDate}.`, { color: MUTED, size: 16 })] }),
    ...(inv.notes ? [muted(inv.notes, 16)] : []),
  ]
}

// ---- Expense note -----------------------------------------------------------
function expenseChildren(e: ExpenseNote, s: Settings, customers: Customer[]): (Paragraph | Table)[] {
  const tot = expenseTotals(e)
  const custName = (id?: string) => customers.find((c) => c.id === id)?.company ?? ''
  const children: (Paragraph | Table)[] = [
    ...masthead(s),
    ...titleBlock('Expense note', monthLabel(e.period)),
    kpiBand([
      { label: 'Reimbursements', value: formatEUR(tot.reimbursementsTotal) },
      { label: 'Mileage', value: formatKm(tot.mileageKm), sub: formatEUR(tot.mileageReimbursement) },
      { label: 'VAT deductible', value: formatEUR(tot.reimbursementsVat) },
      { label: 'Total', value: formatEUR(tot.grandTotal) },
    ]),
    sectionLabel('Reimbursements'),
    e.items.length
      ? dataTable(
          [
            { h: 'Date', w: 14 },
            { h: 'Category', w: 18 },
            { h: 'Description', w: 40 },
            { h: 'Amount', w: 15, right: true },
            { h: 'VAT', w: 13, right: true },
          ],
          e.items.map((i) => [
            i.date,
            i.category,
            `${i.description}${i.supplier ? ` — ${i.supplier}` : ''}`,
            formatEUR(i.amount),
            { text: formatEUR(i.vatAmount ?? 0), muted: true },
          ]),
        )
      : muted('No reimbursements.'),
    sectionLabel(`Mileage — ${formatNumber(e.mileageRatePerKm)} €/km`),
    e.trips.length
      ? dataTable(
          [
            { h: 'Date', w: 13 },
            { h: 'From → To', w: 22 },
            { h: 'Purpose / client', w: 27 },
            { h: 'RT', w: 8, right: true },
            { h: 'Km', w: 14, right: true },
            { h: 'Amount', w: 16, right: true },
          ],
          e.trips.map((tr) => [
            tr.date,
            `${tr.departure} → ${tr.destination}`,
            { text: `${tr.purpose}${tr.customerId ? ` (${custName(tr.customerId)})` : ''}`, muted: true },
            tr.roundTrip ? '×2' : '—',
            formatKm(reimbursableKm(tr)),
            formatEUR(tripReimbursement(tr, e.mileageRatePerKm)),
          ]),
        )
      : muted('No trips.'),
    spacer(80),
    totalsBlock([
      { label: 'Reimbursements', value: formatEUR(tot.reimbursementsTotal) },
      { label: `Mileage (${formatKm(tot.mileageKm)})`, value: formatEUR(tot.mileageReimbursement) },
      { label: 'Total', value: formatEUR(tot.grandTotal), strong: true },
    ]),
  ]
  return children
}

export const wordGenerator: DocumentGenerator = {
  format: 'docx',
  timesheet: (ts, s, customers) => pack(timesheetChildren(ts, s, customers), s),
  invoice: (i, s, customers) => pack(invoiceChildren(i, s, customers), s),
  expense: (e, s, customers) => pack(expenseChildren(e, s, customers), s),
}
