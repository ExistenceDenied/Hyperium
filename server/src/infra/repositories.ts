import { periodKey } from '@af/core'
import type {
  ArchiveRepository,
  Customer,
  CustomerRepository,
  ExpenseNote,
  ExpenseRepository,
  GeneratedDocument,
  Invoice,
  InvoiceRepository,
  Settings,
  SettingsRepository,
  Timesheet,
  TimesheetRepository,
} from '@af/core'
import { db } from './db.js'

export const settingsRepo: SettingsRepository = {
  async get() {
    await db.ensureLoaded()
    return db.get().settings
  },
  async save(s: Settings) {
    return db.mutate((d) => {
      d.settings = s
      return s
    })
  },
}

/** Customers are their own top-level collection, referenced by invoices,
 *  timesheets and expenses. Kept separate from settings so customer edits never
 *  round-trip the singleton config (and its invoice counter). */
export const customerRepo: CustomerRepository = {
  async list() {
    await db.ensureLoaded()
    return [...db.get().customers]
  },
  async get(id) {
    await db.ensureLoaded()
    return db.get().customers.find((c) => c.id === id)
  },
  async save(customer: Customer) {
    return db.mutate((d) => {
      const i = d.customers.findIndex((c) => c.id === customer.id)
      if (i >= 0) d.customers[i] = customer
      else d.customers.push(customer)
      return customer
    })
  },
  async remove(id) {
    await db.mutate((d) => {
      d.customers = d.customers.filter((c) => c.id !== id)
    })
  },
}

export const timesheetRepo: TimesheetRepository = {
  async list() {
    await db.ensureLoaded()
    return [...db.get().timesheets]
  },
  async get(id) {
    await db.ensureLoaded()
    return db.get().timesheets.find((t) => t.id === id)
  },
  async getByPeriodKey(key) {
    await db.ensureLoaded()
    return db.get().timesheets.find((t) => periodKey(t.period) === key)
  },
  async save(t: Timesheet) {
    return db.mutate((d) => {
      const i = d.timesheets.findIndex((x) => x.id === t.id)
      if (i >= 0) d.timesheets[i] = t
      else d.timesheets.push(t)
      return t
    })
  },
  async remove(id) {
    await db.mutate((d) => {
      d.timesheets = d.timesheets.filter((t) => t.id !== id)
    })
  },
}

export const invoiceRepo: InvoiceRepository = {
  async list() {
    await db.ensureLoaded()
    return [...db.get().invoices]
  },
  async get(id) {
    await db.ensureLoaded()
    return db.get().invoices.find((i) => i.id === id)
  },
  async save(inv: Invoice) {
    return db.mutate((d) => {
      const i = d.invoices.findIndex((x) => x.id === inv.id)
      if (i >= 0) d.invoices[i] = inv
      else d.invoices.push(inv)
      return inv
    })
  },
  async remove(id) {
    await db.mutate((d) => {
      d.invoices = d.invoices.filter((i) => i.id !== id)
    })
  },
}

/**
 * Create an invoice atomically: read the next sequence number, build the invoice
 * from it, persist the invoice, and advance the counter — all inside one
 * serialised mutation. This closes the race where two concurrent creates read the
 * same `nextInvoiceSeq` and produce duplicate invoice numbers and structured
 * references. `build` receives the allocated seq and returns the finished invoice.
 */
export async function createInvoiceAtomic(build: (seq: number) => Invoice): Promise<Invoice> {
  return db.mutate((d) => {
    const seq = d.settings.company.nextInvoiceSeq
    const invoice = build(seq)
    d.invoices.push(invoice)
    d.settings.company = { ...d.settings.company, nextInvoiceSeq: seq + 1 }
    return invoice
  })
}

export const expenseRepo: ExpenseRepository = {
  async list() {
    await db.ensureLoaded()
    return [...db.get().expenses]
  },
  async get(id) {
    await db.ensureLoaded()
    return db.get().expenses.find((e) => e.id === id)
  },
  async getByPeriodKey(key) {
    await db.ensureLoaded()
    return db.get().expenses.find((e) => periodKey(e.period) === key)
  },
  async save(e: ExpenseNote) {
    return db.mutate((d) => {
      const i = d.expenses.findIndex((x) => x.id === e.id)
      if (i >= 0) d.expenses[i] = e
      else d.expenses.push(e)
      return e
    })
  },
  async remove(id) {
    await db.mutate((d) => {
      d.expenses = d.expenses.filter((e) => e.id !== id)
    })
  },
}

export const archiveRepo: ArchiveRepository = {
  async list() {
    await db.ensureLoaded()
    return [...db.get().archive].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
  },
  async get(id) {
    await db.ensureLoaded()
    return db.get().archive.find((a) => a.id === id)
  },
  async add(doc: GeneratedDocument) {
    return db.mutate((d) => {
      d.archive.push(doc)
      return doc
    })
  },
  async remove(id) {
    return db.mutate((d) => {
      const doc = d.archive.find((a) => a.id === id)
      d.archive = d.archive.filter((a) => a.id !== id)
      return doc
    })
  },
}

/**
 * Rename an archived document's display title. The on-disk filename stays fixed
 * (it is deterministic and versioned); only the human-facing title changes.
 */
export async function renameArchiveTitle(id: string, title: string): Promise<GeneratedDocument | undefined> {
  return db.mutate((d) => {
    const doc = d.archive.find((a) => a.id === id)
    if (doc) doc.title = title
    return doc
  })
}
