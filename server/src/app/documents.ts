import { randomUUID } from 'node:crypto'
import { monthLabel, periodKey } from '@af/core'
import type { DocFormat, DocKind, GeneratedDocument, Settings } from '@af/core'
import { archiveRepo, expenseRepo, invoiceRepo, settingsRepo, timesheetRepo } from '../infra/repositories.js'
import { documentStore } from '../infra/documentStore.js'
import { pdfGenerator } from '../infra/pdf.js'
import { wordGenerator } from '../infra/word.js'

const generators = { pdf: pdfGenerator, docx: wordGenerator }

const slug = (s: string) => s.replace(/[^a-z0-9]+/gi, '-').replace(/^-+|-+$/g, '').toLowerCase()

interface Resolved {
  bytes: Uint8Array
  title: string
  periodKey?: string
  number?: string
  baseName: string
}

async function resolve(kind: DocKind, refId: string, format: DocFormat, s: Settings): Promise<Resolved> {
  const gen = generators[format]
  if (kind === 'timesheet') {
    const t = await timesheetRepo.get(refId)
    if (!t) throw new Error('Timesheet not found')
    return {
      bytes: await gen.timesheet(t, s),
      title: `Timesheet — ${monthLabel(t.period)}`,
      periodKey: periodKey(t.period),
      baseName: `timesheet-${periodKey(t.period)}`,
    }
  }
  if (kind === 'invoice') {
    const inv = await invoiceRepo.get(refId)
    if (!inv) throw new Error('Invoice not found')
    return {
      bytes: await gen.invoice(inv, s),
      title: `Invoice ${inv.number}`,
      number: inv.number,
      baseName: `invoice-${slug(inv.number)}`,
    }
  }
  const e = await expenseRepo.get(refId)
  if (!e) throw new Error('Expense note not found')
  return {
    bytes: await gen.expense(e, s),
    title: `Expense note — ${monthLabel(e.period)}`,
    periodKey: periodKey(e.period),
    baseName: `expense-${periodKey(e.period)}`,
  }
}

/** Generate a document, store the bytes on disk with version history, and record it in the archive. */
export async function generateDocument(kind: DocKind, refId: string, format: DocFormat): Promise<GeneratedDocument> {
  const settings = await settingsRepo.get()
  const r = await resolve(kind, refId, format, settings)

  const existing = (await archiveRepo.list()).filter((d) => d.kind === kind && d.refId === refId && d.format === format)
  const version = existing.length + 1
  const filename = `${r.baseName}-v${version}.${format}`

  const { relPath, sizeBytes } = await documentStore.save(kind, filename, r.bytes)
  const doc: GeneratedDocument = {
    id: randomUUID(),
    kind,
    refId,
    title: r.title,
    periodKey: r.periodKey,
    number: r.number,
    format,
    filename,
    relPath,
    sizeBytes,
    version,
    createdAt: new Date().toISOString(),
  }
  return archiveRepo.add(doc)
}
