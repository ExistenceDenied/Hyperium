import type {
  DocFormat,
  DocKind,
  ExpenseNote,
  GeneratedDocument,
  Invoice,
  Settings,
  Timesheet,
} from '../domain/entities'

// ---- Repositories -----------------------------------------------------------
export interface SettingsRepository {
  get(): Promise<Settings>
  save(s: Settings): Promise<Settings>
}
export interface TimesheetRepository {
  list(): Promise<Timesheet[]>
  get(id: string): Promise<Timesheet | undefined>
  getByPeriodKey(key: string): Promise<Timesheet | undefined>
  save(t: Timesheet): Promise<Timesheet>
  remove(id: string): Promise<void>
}
export interface InvoiceRepository {
  list(): Promise<Invoice[]>
  get(id: string): Promise<Invoice | undefined>
  save(i: Invoice): Promise<Invoice>
  remove(id: string): Promise<void>
}
export interface ExpenseRepository {
  list(): Promise<ExpenseNote[]>
  get(id: string): Promise<ExpenseNote | undefined>
  getByPeriodKey(key: string): Promise<ExpenseNote | undefined>
  save(e: ExpenseNote): Promise<ExpenseNote>
  remove(id: string): Promise<void>
}
export interface ArchiveRepository {
  list(): Promise<GeneratedDocument[]>
  get(id: string): Promise<GeneratedDocument | undefined>
  add(doc: GeneratedDocument): Promise<GeneratedDocument>
  remove(id: string): Promise<GeneratedDocument | undefined>
}

// ---- Document generation (ports) --------------------------------------------
/** Renders a domain object to document bytes. Implemented in infrastructure (pdfmake / docx). */
export interface DocumentGenerator {
  format: DocFormat
  timesheet(t: Timesheet, s: Settings): Promise<Uint8Array>
  invoice(i: Invoice, s: Settings): Promise<Uint8Array>
  expense(e: ExpenseNote, s: Settings): Promise<Uint8Array>
}

/** Persists generated document bytes to disk (or any store) and returns where it landed. */
export interface DocumentStore {
  save(kind: DocKind, filename: string, bytes: Uint8Array): Promise<{ relPath: string; sizeBytes: number }>
  read(relPath: string): Promise<Uint8Array>
  remove(relPath: string): Promise<void>
  absolutePath(relPath: string): string
}

// ---- Ambient services -------------------------------------------------------
export interface Clock {
  now(): Date
}
export interface IdGen {
  next(): string
}

// ---- Future extension points (ports only; no adapters yet) ------------------
// Documented so each future integration is a new adapter, not a rewrite.
export interface AccountingExporter {
  readonly target: string // 'exact' | 'yuki' | 'odoo' | …
  exportInvoice(i: Invoice): Promise<void>
}
export interface EInvoiceSender {
  send(i: Invoice): Promise<{ id: string }>
}
export interface OcrService {
  extract(bytes: Uint8Array): Promise<{ amount?: number; vatAmount?: number; supplier?: string; date?: string }>
}
