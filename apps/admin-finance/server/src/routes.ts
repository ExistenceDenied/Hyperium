import { randomUUID } from 'node:crypto'
import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify'
import {
  accountingCsv,
  buildInvoice,
  CommentSchema,
  currentPeriod,
  CustomerSchema,
  DocStatusSchema,
  monthlyDashboard,
  parseCoda,
  parsePeriodKey,
  reconcile,
  SettingsSchema,
  TimesheetSchema,
  ExpenseNoteSchema,
  InvoiceSchema,
  InvoiceLineSchema,
} from '@af/core'
import { z } from 'zod'
import type { ExpenseNote, Invoice, Timesheet } from '@af/core'
import {
  archiveRepo,
  createInvoiceAtomic,
  customerRepo,
  expenseRepo,
  invoiceRepo,
  renameArchiveTitle,
  settingsRepo,
  timesheetRepo,
} from './infra/repositories.js'
import { documentStore } from './infra/documentStore.js'
import { generateDocument } from './app/documents.js'
import { buildQuarterPackage } from './app/quarter-package.js'

const nowIso = () => new Date().toISOString()

export async function registerRoutes(app: FastifyInstance): Promise<void> {
  app.get('/api/health', async () => ({ ok: true, service: 'admin-finance', time: nowIso() }))

  // ---- Settings -------------------------------------------------------------
  app.get('/api/settings', async () => settingsRepo.get())
  app.put('/api/settings', async (req) => {
    const parsed = SettingsSchema.parse(req.body)
    return settingsRepo.save(parsed)
  })

  // ---- Customers (a top-level collection, not part of settings) -------------
  app.get('/api/customers', async () => customerRepo.list())
  app.get('/api/customers/:id', async (req, reply) => {
    const { id } = req.params as { id: string }
    const c = await customerRepo.get(id)
    if (!c) return reply.code(404).send({ error: 'not found' })
    return c
  })
  app.post('/api/customers', async (req) => {
    const customer = CustomerSchema.parse(req.body)
    return customerRepo.save(customer)
  })
  app.put('/api/customers/:id', async (req) => {
    const { id } = req.params as { id: string }
    const customer = CustomerSchema.parse({ ...(req.body as object), id })
    return customerRepo.save(customer)
  })
  app.delete('/api/customers/:id', async (req) => {
    await customerRepo.remove((req.params as { id: string }).id)
    return { ok: true }
  })

  // ---- Timesheets -----------------------------------------------------------
  app.get('/api/timesheets', async () => timesheetRepo.list())
  app.get('/api/timesheets/:id', async (req, reply) => {
    const { id } = req.params as { id: string }
    const t = await timesheetRepo.get(id)
    if (!t) return reply.code(404).send({ error: 'not found' })
    return t
  })
  // Get-or-create the timesheet for a period (persisted so ids are stable).
  app.get('/api/timesheets/period/:key', async (req) => {
    const { key } = req.params as { key: string }
    const existing = await timesheetRepo.getByPeriodKey(key)
    if (existing) return existing
    const t: Timesheet = {
      id: randomUUID(),
      period: parsePeriodKey(key),
      days: [],
      status: 'draft',
      comments: [],
      createdAt: nowIso(),
      updatedAt: nowIso(),
    }
    return timesheetRepo.save(t)
  })
  app.put('/api/timesheets/:id', async (req) => {
    const { id } = req.params as { id: string }
    const parsed = TimesheetSchema.parse({ ...(req.body as object), id })
    parsed.updatedAt = nowIso()
    return timesheetRepo.save(parsed)
  })

  // ---- Invoices -------------------------------------------------------------
  app.get('/api/invoices', async () => invoiceRepo.list())
  app.get('/api/invoices/:id', async (req, reply) => {
    const { id } = req.params as { id: string }
    const inv = await invoiceRepo.get(id)
    if (!inv) return reply.code(404).send({ error: 'not found' })
    return inv
  })

  const CreateInvoiceBody = z.object({
    customerId: z.string(),
    date: z.string(),
    timesheetId: z.string().optional(),
    basis: z.enum(['day', 'hour']).optional(),
    vatTreatment: z.enum(['standard', 'reverse_charge_eu', 'exempt', 'zero']).optional(),
    paymentTermsDays: z.number().int().nonnegative().optional(),
    reference: z.string().optional(),
    extraLines: z.array(InvoiceLineSchema).optional(),
    notes: z.string().optional(),
  })
  app.post('/api/invoices', async (req, reply) => {
    const body = CreateInvoiceBody.parse(req.body)
    const settings = await settingsRepo.get()
    const customer = await customerRepo.get(body.customerId)
    if (!customer) return reply.code(400).send({ error: 'unknown customer' })
    const timesheet = body.timesheetId ? await timesheetRepo.get(body.timesheetId) : undefined
    const year = (timesheet?.period ?? currentPeriod(new Date())).year
    // Allocate the sequence, build, persist, and advance the counter in one
    // atomic mutation — concurrent creates can never share an invoice number.
    return createInvoiceAtomic((seq) =>
      buildInvoice({
        id: randomUUID(),
        year,
        seq,
        date: body.date,
        company: settings.company,
        customer,
        timesheet,
        basis: body.basis,
        extraLines: body.extraLines,
        standardVatRatePct: settings.financial.standardVatRatePct,
        vatTreatment: body.vatTreatment,
        paymentTermsDays: body.paymentTermsDays,
        reference: body.reference,
        notes: body.notes,
        createdAt: nowIso(),
      }),
    )
  })
  app.put('/api/invoices/:id', async (req, reply) => {
    const { id } = req.params as { id: string }
    const current = await invoiceRepo.get(id)
    if (!current) return reply.code(404).send({ error: 'not found' })
    // Validate the whole record, then force the legal-identity fields back to
    // their originals: number, sequence, year and structured reference are fixed
    // once an invoice exists and must never change on edit. createdAt is kept too.
    const parsed = InvoiceSchema.parse({ ...current, ...(req.body as object), id })
    const updated: Invoice = {
      ...parsed,
      number: current.number,
      seq: current.seq,
      year: current.year,
      structuredReference: current.structuredReference,
      createdAt: current.createdAt,
    }
    return invoiceRepo.save(updated)
  })

  // ---- Expense notes --------------------------------------------------------
  app.get('/api/expenses', async () => expenseRepo.list())
  app.get('/api/expenses/:id', async (req, reply) => {
    const { id } = req.params as { id: string }
    const e = await expenseRepo.get(id)
    if (!e) return reply.code(404).send({ error: 'not found' })
    return e
  })
  app.get('/api/expenses/period/:key', async (req) => {
    const { key } = req.params as { key: string }
    const existing = await expenseRepo.getByPeriodKey(key)
    if (existing) return existing
    const settings = await settingsRepo.get()
    const e: ExpenseNote = {
      id: randomUUID(),
      period: parsePeriodKey(key),
      items: [],
      trips: [],
      mileageRatePerKm: settings.financial.mileageRatePerKm,
      status: 'draft',
      comments: [],
      createdAt: nowIso(),
      updatedAt: nowIso(),
    }
    return expenseRepo.save(e)
  })
  app.put('/api/expenses/:id', async (req) => {
    const { id } = req.params as { id: string }
    const parsed = ExpenseNoteSchema.parse({ ...(req.body as object), id })
    parsed.updatedAt = nowIso()
    return expenseRepo.save(parsed)
  })

  // ---- Dashboard ------------------------------------------------------------
  app.get('/api/dashboard/:key', async (req) => {
    const { key } = req.params as { key: string }
    const period = parsePeriodKey(key)
    const timesheet = await timesheetRepo.getByPeriodKey(key)
    const expenseNote = await expenseRepo.getByPeriodKey(key)
    const invoices = (await invoiceRepo.list()).filter((inv) => inv.date.slice(0, 7) === key)
    return monthlyDashboard({ period, timesheet, invoices, expenseNote })
  })

  // ---- Accounting export ----------------------------------------------------
  // Returns a generic, import-mappable CSV of invoices (a sales journal) as a
  // LOCAL file the owner imports into Exact/Yuki/Odoo. It never pushes anywhere
  // and needs no credentials — read-only over the data.
  const ExportQuery = z.object({ period: z.string().regex(/^\d{4}-\d{2}$/).optional() })
  app.get('/api/exports/accounting', async (req) => {
    const { period } = ExportQuery.parse(req.query ?? {})
    const customers = await customerRepo.list()
    let invoices = await invoiceRepo.list()
    if (period) invoices = invoices.filter((i) => i.date.startsWith(period))
    return {
      filename: `accounting-export-${period ?? 'all'}.csv`,
      invoiceCount: invoices.length,
      content: accountingCsv(invoices, customers),
    }
  })

  // Everything an accountant needs for a quarter's VAT processing, as one ZIP
  // (invoice + expense PDFs, the accounting CSV, and a VAT summary). Local file
  // for hand-off — never sent anywhere.
  app.get('/api/exports/quarter/:q', async (req, reply) => {
    const { q } = req.params as { q: string }
    let pkg
    try {
      pkg = await buildQuarterPackage(q)
    } catch (err) {
      return reply.code(400).send({ error: err instanceof Error ? err.message : String(err) })
    }
    reply.header('Content-Type', 'application/zip')
    reply.header('Content-Disposition', `attachment; filename="${pkg.filename}"`)
    reply.header('X-Invoice-Count', String(pkg.invoiceCount))
    reply.header('X-Expense-Count', String(pkg.expenseCount))
    return reply.send(pkg.bytes)
  })

  // ---- Bank reconciliation (CODA) ------------------------------------------
  // Match a CODA bank statement against invoices (income, via the structured
  // reference) and expense items (spending, by amount), and surface anything
  // without a supporting document. The .cod content is parsed locally; no bank
  // connection, no credentials, nothing sent anywhere.
  const ReconcileBody = z.object({ coda: z.string().min(1) })
  app.post('/api/reconcile', async (req, reply) => {
    const { coda } = ReconcileBody.parse(req.body)
    const movements = parseCoda(coda)
    if (movements.length === 0) {
      return reply.code(400).send({ error: 'no CODA movement records (2.1) found — is this a .cod file?' })
    }
    const invoices = await invoiceRepo.list()
    const expenses = await expenseRepo.list()
    return { movementCount: movements.length, ...reconcile(movements, invoices, expenses) }
  })

  // ---- Archive + document generation ---------------------------------------
  app.get('/api/archive', async () => archiveRepo.list())
  const GenBody = z.object({
    kind: z.enum(['timesheet', 'invoice', 'expense']),
    refId: z.string(),
    format: z.enum(['pdf', 'docx']),
  })
  app.post('/api/documents', async (req) => {
    const { kind, refId, format } = GenBody.parse(req.body)
    return generateDocument(kind, refId, format)
  })
  // The trailing :filename segment is cosmetic — it makes browsers name the
  // downloaded file correctly even if they ignore the Content-Disposition header.
  const download = async (req: FastifyRequest, reply: FastifyReply) => {
    const { id } = req.params as { id: string }
    const doc = await archiveRepo.get(id)
    if (!doc) return reply.code(404).send({ error: 'not found' })
    const bytes = await documentStore.read(doc.relPath)
    const mime =
      doc.format === 'pdf'
        ? 'application/pdf'
        : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    const inline = (req.query as { inline?: string } | undefined)?.inline !== undefined
    reply.header('Content-Type', mime)
    reply.header('Content-Disposition', `${inline ? 'inline' : 'attachment'}; filename="${doc.filename}"`)
    return reply.send(Buffer.from(bytes))
  }
  app.get('/api/archive/:id/download', download)
  app.get('/api/archive/:id/download/:filename', download)
  // Resolve the absolute on-disk path of an archived file. The API is the only
  // component that knows its own data directory (AF_DATA_DIR), so it is the
  // source of truth — clients must not compute this themselves.
  app.get('/api/archive/:id/path', async (req, reply) => {
    const { id } = req.params as { id: string }
    const doc = await archiveRepo.get(id)
    if (!doc) return reply.code(404).send({ error: 'not found' })
    return {
      id: doc.id,
      filename: doc.filename,
      relPath: doc.relPath,
      absolutePath: documentStore.absolutePath(doc.relPath),
    }
  })
  // Rename an archived document's display title (the file on disk is unchanged).
  app.patch('/api/archive/:id', async (req, reply) => {
    const { id } = req.params as { id: string }
    const { title } = z.object({ title: z.string().min(1) }).parse(req.body)
    const updated = await renameArchiveTitle(id, title)
    if (!updated) return reply.code(404).send({ error: 'not found' })
    return updated
  })

  // ---- Status + comments (workflow) ----------------------------------------
  const MetaBody = z.object({
    status: DocStatusSchema.optional(),
    comments: z.array(CommentSchema).optional(),
  })
  interface MetaRepo {
    get(id: string): Promise<{ id: string } | undefined>
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    save(x: any): Promise<unknown>
  }
  const registerMeta = (base: string, repo: MetaRepo) =>
    app.patch(`${base}/:id/meta`, async (req, reply) => {
      const { id } = req.params as { id: string }
      const body = MetaBody.parse(req.body)
      const cur = await repo.get(id)
      if (!cur) return reply.code(404).send({ error: 'not found' })
      return repo.save({ ...cur, ...body })
    })
  registerMeta('/api/timesheets', timesheetRepo)
  registerMeta('/api/invoices', invoiceRepo)
  registerMeta('/api/expenses', expenseRepo)

  // ---- Delete --------------------------------------------------------------
  const deleteDeliverable = async (id: string, remove: (id: string) => Promise<void>) => {
    for (const d of (await archiveRepo.list()).filter((a) => a.refId === id)) {
      await documentStore.remove(d.relPath)
      await archiveRepo.remove(d.id)
    }
    await remove(id)
  }
  app.delete('/api/timesheets/:id', async (req) => {
    await deleteDeliverable((req.params as { id: string }).id, timesheetRepo.remove)
    return { ok: true }
  })
  app.delete('/api/invoices/:id', async (req) => {
    await deleteDeliverable((req.params as { id: string }).id, invoiceRepo.remove)
    return { ok: true }
  })
  app.delete('/api/expenses/:id', async (req) => {
    await deleteDeliverable((req.params as { id: string }).id, expenseRepo.remove)
    return { ok: true }
  })
  app.delete('/api/archive/:id', async (req) => {
    const doc = await archiveRepo.remove((req.params as { id: string }).id)
    if (doc) await documentStore.remove(doc.relPath)
    return { ok: true }
  })
}
