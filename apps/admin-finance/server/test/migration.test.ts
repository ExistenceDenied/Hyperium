import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, rm, writeFile, readFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import type { FastifyInstance } from 'fastify'

// A db.json in the OLD shape: customers nested under settings, no top-level list.
const OLD_DB = {
  settings: {
    company: {
      name: 'Legacy BV',
      legalForm: 'BV',
      vatNumber: '',
      addressLines: [],
      iban: '',
      bic: '',
      email: '',
      phone: '',
      invoiceNumberFormat: '{year}-{seq:3}',
      nextInvoiceSeq: 7,
    },
    financial: { standardVatRatePct: 21, mileageRatePerKm: 0.4415, defaultTemplate: 'default' },
    customers: [
      { id: 'legacy1', company: 'Legacy Client', contactPerson: '', addressLines: [], vatNumber: '', email: '', defaultDayRate: 900, defaultHourlyRate: 100, paymentTermsDays: 30, vatTreatment: 'standard' },
    ],
  },
  timesheets: [],
  invoices: [],
  expenses: [],
  archive: [],
}

let app: FastifyInstance
let dataDir: string
let dbFile: string

before(async () => {
  dataDir = await mkdtemp(join(tmpdir(), 'af-migrate-'))
  dbFile = join(dataDir, 'db.json')
  await writeFile(dbFile, JSON.stringify(OLD_DB, null, 2), 'utf8')
  process.env.AF_DATA_DIR = dataDir
  const { buildApp } = await import('../src/app.ts')
  app = await buildApp({ logger: false }) // ensureLoaded runs the migration + flush here
})
after(async () => {
  await app?.close()
  if (dataDir) await rm(dataDir, { recursive: true, force: true })
})

const get = async (url: string) => {
  const res = await app.inject({ method: 'GET', url })
  return { status: res.statusCode, body: JSON.parse(res.payload) }
}

test('legacy settings.customers are silently hoisted to a top-level collection', async () => {
  const customers = await get('/api/customers')
  assert.equal(customers.body.length, 1)
  assert.equal(customers.body[0].company, 'Legacy Client')

  const settings = await get('/api/settings')
  assert.equal(settings.body.company.name, 'Legacy BV')
  assert.equal(settings.body.company.nextInvoiceSeq, 7) // config preserved, counter intact
  assert.equal(settings.body.customers, undefined) // no longer nested in settings
})

test('the db file on disk is rewritten in the new shape', async () => {
  const onDisk = JSON.parse(await readFile(dbFile, 'utf8'))
  assert.ok(Array.isArray(onDisk.customers), 'customers should be a top-level array')
  assert.equal(onDisk.customers.length, 1)
  assert.equal(onDisk.customers[0].id, 'legacy1')
  assert.equal(onDisk.settings.customers, undefined, 'settings should no longer carry customers')
})
