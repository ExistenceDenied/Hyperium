import { z } from 'zod'

/** A calendar month (month 1-12). */
export const PeriodSchema = z.object({
  year: z.number().int(),
  month: z.number().int().min(1).max(12),
})

export const VatTreatmentSchema = z.enum(['standard', 'reverse_charge_eu', 'exempt', 'zero'])

// ---- Workflow (status + to-do comments), shared by every deliverable --------
export const DocStatusSchema = z.enum(['draft', 'in_progress', 'ready', 'final'])
export type DocStatus = z.infer<typeof DocStatusSchema>
export const DOC_STATUSES = DocStatusSchema.options

export const CommentSchema = z.object({
  id: z.string(),
  text: z.string(),
  done: z.boolean().default(false),
  createdAt: z.string(),
})
export type Comment = z.infer<typeof CommentSchema>

// ---- Settings ---------------------------------------------------------------
export const CompanySchema = z.object({
  name: z.string().default('Hyperium BV'),
  legalForm: z.string().default('BV'),
  vatNumber: z.string().default(''), // BE0xxx.xxx.xxx
  addressLines: z.array(z.string()).default([]),
  iban: z.string().default(''),
  bic: z.string().default(''),
  email: z.string().default(''),
  phone: z.string().default(''),
  invoiceNumberFormat: z.string().default('{year}-{seq:3}'), // tokens: {year} {seq} {seq:N}
  nextInvoiceSeq: z.number().int().min(1).default(1),
})
export type Company = z.infer<typeof CompanySchema>

export const CustomerSchema = z.object({
  id: z.string(),
  company: z.string().min(1),
  contactPerson: z.string().default(''),
  addressLines: z.array(z.string()).default([]),
  vatNumber: z.string().default(''),
  email: z.string().default(''),
  defaultDayRate: z.number().nonnegative().default(0),
  defaultHourlyRate: z.number().nonnegative().default(0),
  paymentTermsDays: z.number().int().nonnegative().default(30),
  vatTreatment: VatTreatmentSchema.default('standard'),
})
export type Customer = z.infer<typeof CustomerSchema>

export const FinancialSettingsSchema = z.object({
  standardVatRatePct: z.number().min(0).max(100).default(21),
  mileageRatePerKm: z.number().min(0).default(0.4415), // Belgian forfaitary rate — configurable [verify current]
  defaultTemplate: z.string().default('default'),
})
export type FinancialSettings = z.infer<typeof FinancialSettingsSchema>

// Customers are their own top-level collection (referenced by invoices,
// timesheets and expenses); settings holds only company + financial config.
export const SettingsSchema = z.object({
  company: CompanySchema,
  financial: FinancialSettingsSchema,
})
export type Settings = z.infer<typeof SettingsSchema>

// ---- Timesheet --------------------------------------------------------------
export const TimesheetDaySchema = z.object({
  date: z.string(), // yyyy-MM-dd
  billable: z.boolean().default(true),
  hours: z.number().nonnegative().default(8),
  customerId: z.string().optional(),
  project: z.string().optional(),
  comment: z.string().optional(),
})
export type TimesheetDay = z.infer<typeof TimesheetDaySchema>

export const TimesheetSchema = z.object({
  id: z.string(),
  period: PeriodSchema,
  days: z.array(TimesheetDaySchema).default([]),
  note: z.string().optional(),
  status: DocStatusSchema.default('draft'),
  comments: z.array(CommentSchema).default([]),
  createdAt: z.string(),
  updatedAt: z.string(),
})
export type Timesheet = z.infer<typeof TimesheetSchema>

// ---- Invoice ----------------------------------------------------------------
export const InvoiceLineSchema = z.object({
  description: z.string(),
  quantity: z.number(),
  unit: z.string().default('day'),
  unitPrice: z.number(),
})
export type InvoiceLine = z.infer<typeof InvoiceLineSchema>

export const InvoiceSchema = z.object({
  id: z.string(),
  number: z.string(),
  seq: z.number().int(),
  year: z.number().int(),
  date: z.string(),
  dueDate: z.string(),
  customerId: z.string(),
  timesheetId: z.string().optional(),
  lines: z.array(InvoiceLineSchema),
  vatTreatment: VatTreatmentSchema,
  standardVatRatePct: z.number(),
  structuredReference: z.string(),
  reference: z.string().optional(),
  notes: z.string().optional(),
  status: DocStatusSchema.default('draft'),
  comments: z.array(CommentSchema).default([]),
  createdAt: z.string(),
})
export type Invoice = z.infer<typeof InvoiceSchema>

// ---- Expense note -----------------------------------------------------------
export const ExpenseItemSchema = z.object({
  id: z.string(),
  date: z.string(),
  category: z.string().default(''),
  description: z.string().default(''),
  supplier: z.string().default(''),
  amount: z.number().default(0),
  vatAmount: z.number().default(0),
  attachmentId: z.string().optional(),
  attachmentName: z.string().optional(),
  status: z.enum(['draft', 'submitted', 'reimbursed']).default('draft'),
})
export type ExpenseItem = z.infer<typeof ExpenseItemSchema>

export const MileageTripSchema = z.object({
  id: z.string(),
  date: z.string(),
  departure: z.string().default(''),
  destination: z.string().default(''),
  purpose: z.string().default(''),
  customerId: z.string().optional(),
  distanceKm: z.number().nonnegative().default(0),
  roundTrip: z.boolean().default(false),
})
export type MileageTrip = z.infer<typeof MileageTripSchema>

export const ExpenseNoteSchema = z.object({
  id: z.string(),
  period: PeriodSchema,
  items: z.array(ExpenseItemSchema).default([]),
  trips: z.array(MileageTripSchema).default([]),
  mileageRatePerKm: z.number(),
  status: DocStatusSchema.default('draft'),
  comments: z.array(CommentSchema).default([]),
  createdAt: z.string(),
  updatedAt: z.string(),
})
export type ExpenseNote = z.infer<typeof ExpenseNoteSchema>

// ---- Archive ----------------------------------------------------------------
export const DocKindSchema = z.enum(['timesheet', 'invoice', 'expense'])
export type DocKind = z.infer<typeof DocKindSchema>
export const DocFormatSchema = z.enum(['pdf', 'docx'])
export type DocFormat = z.infer<typeof DocFormatSchema>

export const GeneratedDocumentSchema = z.object({
  id: z.string(),
  kind: DocKindSchema,
  refId: z.string(),
  title: z.string(),
  periodKey: z.string().optional(),
  number: z.string().optional(),
  format: DocFormatSchema,
  filename: z.string(),
  relPath: z.string(), // relative to data/
  sizeBytes: z.number(),
  version: z.number().int(),
  createdAt: z.string(),
})
export type GeneratedDocument = z.infer<typeof GeneratedDocumentSchema>
