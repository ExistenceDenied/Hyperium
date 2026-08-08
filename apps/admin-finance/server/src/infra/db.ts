import { mkdir, readFile, rename, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { dirname } from 'node:path'
import {
  Customer,
  CustomerSchema,
  ExpenseNote,
  ExpenseNoteSchema,
  GeneratedDocument,
  Invoice,
  InvoiceSchema,
  Settings,
  SettingsSchema,
  Timesheet,
  TimesheetSchema,
} from '@af/core'
import { DATA_DIR, DB_FILE } from './paths.js'

export interface DbShape {
  settings: Settings
  customers: Customer[]
  timesheets: Timesheet[]
  invoices: Invoice[]
  expenses: ExpenseNote[]
  archive: GeneratedDocument[]
}

const defaultDb = (): DbShape => ({
  settings: SettingsSchema.parse({ company: {}, financial: {} }),
  customers: [],
  timesheets: [],
  invoices: [],
  expenses: [],
  archive: [],
})

/** Tiny durable JSON store. All writes go through the in-memory copy then flush atomically-ish. */
export class Db {
  private data: DbShape = defaultDb()
  private loaded = false
  private queue: Promise<void> = Promise.resolve()

  async ensureLoaded(): Promise<void> {
    if (this.loaded) return
    await mkdir(DATA_DIR, { recursive: true })
    if (existsSync(DB_FILE)) {
      const raw = await readFile(DB_FILE, 'utf8')
      // Older files nested customers under settings; read from there when the
      // top-level collection is absent. On the next flush the file is rewritten
      // in the new shape (customers top-level, settings without them) — a silent,
      // one-way migration. SettingsSchema no longer has `customers`, so parsing
      // settings drops the legacy key automatically.
      const parsed = JSON.parse(raw) as Partial<DbShape> & { settings?: { customers?: unknown[] } }
      const legacyCustomers = Array.isArray(parsed.settings?.customers) ? parsed.settings.customers : []
      const rawCustomers = parsed.customers ?? legacyCustomers
      // Parse each record through its schema so older data gains any new
      // fields (e.g. status / comments) via their defaults.
      this.data = {
        settings: SettingsSchema.parse(parsed.settings ?? { company: {}, financial: {} }),
        customers: rawCustomers.map((c) => CustomerSchema.parse(c)),
        timesheets: (parsed.timesheets ?? []).map((t) => TimesheetSchema.parse(t)),
        invoices: (parsed.invoices ?? []).map((i) => InvoiceSchema.parse(i)),
        expenses: (parsed.expenses ?? []).map((e) => ExpenseNoteSchema.parse(e)),
        archive: parsed.archive ?? [],
      }
      if (parsed.customers === undefined && legacyCustomers.length > 0) await this.flush()
    } else {
      await this.flush()
    }
    this.loaded = true
  }

  get(): DbShape {
    return this.data
  }

  /** Serialise writes so concurrent requests don't clobber the file. */
  async mutate<T>(fn: (d: DbShape) => T): Promise<T> {
    await this.ensureLoaded()
    let result!: T
    this.queue = this.queue.then(async () => {
      result = fn(this.data)
      await this.flush()
    })
    await this.queue
    return result
  }

  private async flush(): Promise<void> {
    await mkdir(dirname(DB_FILE), { recursive: true })
    // Write to a sibling temp file, then atomically rename it over the real one.
    // A crash — or a OneDrive sync / antivirus touching the file mid-write — can
    // then never leave a truncated db.json, the file that *is* the records.
    const tmp = `${DB_FILE}.${process.pid}.tmp`
    await writeFile(tmp, JSON.stringify(this.data, null, 2), 'utf8')
    await renameWithRetry(tmp, DB_FILE)
  }
}

const delay = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * `rename` is atomic on a single volume, but on Windows a transient lock held by
 * OneDrive sync or antivirus can make it fail with EPERM/EBUSY/EACCES even when
 * nothing is wrong. Retry a few times with a short backoff before giving up; the
 * real db.json is left intact throughout (only the temp file is at risk).
 */
async function renameWithRetry(from: string, to: string, attempts = 5): Promise<void> {
  for (let i = 0; ; i++) {
    try {
      await rename(from, to)
      return
    } catch (err) {
      const code = (err as NodeJS.ErrnoException).code
      const transient = code === 'EPERM' || code === 'EBUSY' || code === 'EACCES'
      if (!transient || i >= attempts - 1) throw err
      await delay(20 * (i + 1))
    }
  }
}

export const db = new Db()
