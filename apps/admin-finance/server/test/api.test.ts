import { test, before, after } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import type { FastifyInstance } from 'fastify'

// The app is built AFTER AF_DATA_DIR is set, so every write lands in a throwaway
// temp directory — the real data/db.json is never touched by the suite.
let app: FastifyInstance
let dataDir: string

before(async () => {
  dataDir = await mkdtemp(join(tmpdir(), 'af-nrt-'))
  process.env.AF_DATA_DIR = dataDir
  const { buildApp } = await import('../src/app.ts')
  app = await buildApp({ logger: false })
})
after(async () => {
  await app?.close()
  if (dataDir) await rm(dataDir, { recursive: true, force: true })
})

async function api(method: string, url: string, body?: unknown) {
  const res = await app.inject({
    method: method as 'GET',
    url,
    ...(body !== undefined
      ? { headers: { 'content-type': 'application/json' }, payload: JSON.stringify(body) }
      : {}),
  })
  let parsed: any
  try {
    parsed = res.payload ? JSON.parse(res.payload) : undefined
  } catch {
    parsed = res.payload
  }
  return { status: res.statusCode, body: parsed, headers: res.headers }
}

const SETTINGS = (nextInvoiceSeq = 1) => ({
  company: {
    name: 'Test BV',
    legalForm: 'BV',
    vatNumber: 'BE0123.456.789',
    addressLines: ['Teststraat 1', '2000 Antwerpen'],
    iban: 'BE68539007547034',
    bic: 'GKCCBEBB',
    email: 'test@example.be',
    phone: '',
    invoiceNumberFormat: '{year}-{seq:3}',
    nextInvoiceSeq,
  },
  financial: { standardVatRatePct: 21, mileageRatePerKm: 0.4415, defaultTemplate: 'default' },
})

const CUSTOMER_C1 = {
  id: 'c1',
  company: 'Client NV',
  contactPerson: 'Jan',
  addressLines: ['Bankstraat 9', '1000 Brussel'],
  vatNumber: 'BE0999.888.777',
  email: 'ap@client.be',
  defaultDayRate: 1000,
  defaultHourlyRate: 125,
  paymentTermsDays: 30,
  vatTreatment: 'standard',
}

let tsId = ''
let invId1 = ''

// ---- health -----------------------------------------------------------------
test('GET /api/health', async () => {
  const r = await api('GET', '/api/health')
  assert.equal(r.status, 200)
  assert.equal(r.body.ok, true)
})

// ---- settings + customer seed -----------------------------------------------
test('settings round-trip (company + financial only)', async () => {
  const put = await api('PUT', '/api/settings', SETTINGS(1))
  assert.equal(put.status, 200)
  const get = await api('GET', '/api/settings')
  assert.equal(get.body.company.nextInvoiceSeq, 1)
  assert.equal(get.body.company.name, 'Test BV')
  // Settings is no longer a home for customers.
  assert.equal(get.body.customers, undefined)
})

test('customers are a top-level collection', async () => {
  const created = await api('POST', '/api/customers', CUSTOMER_C1)
  assert.equal(created.status, 200)
  const list = await api('GET', '/api/customers')
  assert.equal(list.status, 200)
  assert.equal(list.body.length, 1)
  assert.equal(list.body[0].company, 'Client NV')
  // and are NOT surfaced through settings
  const settings = await api('GET', '/api/settings')
  assert.equal(settings.body.customers, undefined)
})

// ---- timesheet CRUD ---------------------------------------------------------
test('timesheet get-or-create for a period, then update days', async () => {
  const created = await api('GET', '/api/timesheets/period/2026-07')
  assert.equal(created.status, 200)
  tsId = created.body.id
  assert.ok(tsId)
  // Same period returns the same persisted record (stable id).
  const again = await api('GET', '/api/timesheets/period/2026-07')
  assert.equal(again.body.id, tsId)

  const withDays = {
    ...created.body,
    days: [
      { date: '2026-07-01', billable: true, hours: 8, customerId: 'c1' },
      { date: '2026-07-02', billable: true, hours: 8, customerId: 'c1' },
      { date: '2026-07-03', billable: true, hours: 8, customerId: 'c1' },
      { date: '2026-07-04', billable: false, hours: 4 },
    ],
  }
  const put = await api('PUT', `/api/timesheets/${tsId}`, withDays)
  assert.equal(put.status, 200)
  assert.equal(put.body.days.length, 4)
})

// ---- invoice create ---------------------------------------------------------
test('POST /api/invoices bills a timesheet by day and advances the sequence', async () => {
  const r = await api('POST', '/api/invoices', {
    customerId: 'c1',
    date: '2026-07-15',
    timesheetId: tsId,
    basis: 'day',
  })
  assert.equal(r.status, 200)
  invId1 = r.body.id
  assert.equal(r.body.number, '2026-001')
  assert.equal(r.body.seq, 1)
  assert.equal(r.body.dueDate, '2026-08-14') // date + 30 day terms
  assert.equal(r.body.lines.length, 1)
  assert.equal(r.body.lines[0].quantity, 3) // 3 billable days
  assert.equal(r.body.lines[0].unitPrice, 1000)
  assert.match(r.body.structuredReference, /^\+\+\+\d{3}\/\d{4}\/\d{5}\+\+\+$/)

  const settings = await api('GET', '/api/settings')
  assert.equal(settings.body.company.nextInvoiceSeq, 2) // advanced by one
})

// ---- dashboard --------------------------------------------------------------
test('GET /api/dashboard aggregates the month', async () => {
  const r = await api('GET', '/api/dashboard/2026-07')
  assert.equal(r.status, 200)
  assert.equal(r.body.revenue, 3000) // 3 days * 1000, ex VAT
  assert.equal(r.body.vatCollected, 630) // 21%
  assert.equal(r.body.billableDays, 3)
})

// ---- expense CRUD -----------------------------------------------------------
test('expense get-or-create, add items + trips, reflected in the dashboard', async () => {
  const created = await api('GET', '/api/expenses/period/2026-07')
  assert.equal(created.status, 200)
  const eId = created.body.id
  const withData = {
    ...created.body,
    items: [
      { id: 'x1', date: '2026-07-05', category: 'Software', description: 'IDE', supplier: 'JB', amount: 289, vatAmount: 50.15, status: 'submitted' },
    ],
    trips: [
      { id: 't1', date: '2026-07-01', departure: 'A', destination: 'B', purpose: 'workshop', distanceKm: 45, roundTrip: true },
      { id: 't2', date: '2026-07-03', departure: 'A', destination: 'C', purpose: 'prospect', distanceKm: 60, roundTrip: false },
    ],
  }
  const put = await api('PUT', `/api/expenses/${eId}`, withData)
  assert.equal(put.status, 200)
  assert.equal(put.body.items.length, 1)

  const dash = await api('GET', '/api/dashboard/2026-07')
  assert.equal(dash.body.expenses, 289)
  assert.equal(dash.body.mileageReimbursement, 66.22) // round2(150 * 0.4415)
})

// ---- archive: generate, rename, download, delete ----------------------------
test('archive document lifecycle (generate -> rename -> download -> delete)', async () => {
  const gen = await api('POST', '/api/documents', { kind: 'invoice', refId: invId1, format: 'pdf' })
  assert.equal(gen.status, 200)
  const docId = gen.body.id
  assert.equal(gen.body.version, 1)
  assert.equal(gen.body.format, 'pdf')
  const origFilename = gen.body.filename

  const list = await api('GET', '/api/archive')
  assert.ok(list.body.some((d: any) => d.id === docId))

  // Rename changes the title only; the on-disk filename is preserved.
  const renamed = await api('PATCH', `/api/archive/${docId}`, { title: 'Renamed invoice' })
  assert.equal(renamed.status, 200)
  assert.equal(renamed.body.title, 'Renamed invoice')
  assert.equal(renamed.body.filename, origFilename)

  const empty = await api('PATCH', `/api/archive/${docId}`, { title: '' })
  assert.ok(empty.status >= 400) // empty title rejected
  const missing = await api('PATCH', '/api/archive/nope', { title: 'x' })
  assert.equal(missing.status, 404)

  const dl = await api('GET', `/api/archive/${docId}/download`)
  assert.equal(dl.status, 200)
  assert.equal(dl.headers['content-type'], 'application/pdf')

  const del = await api('DELETE', `/api/archive/${docId}`)
  assert.equal(del.status, 200)
  const after = await api('GET', '/api/archive')
  assert.ok(!after.body.some((d: any) => d.id === docId))
})

// ---- the API resolves absolute paths against its OWN data dir ---------------
test('GET /api/archive/:id/path returns an absolute path rooted in AF_DATA_DIR', async () => {
  const gen = await api('POST', '/api/documents', { kind: 'invoice', refId: invId1, format: 'pdf' })
  assert.equal(gen.status, 200)
  const docId = gen.body.id

  const path = await api('GET', `/api/archive/${docId}/path`)
  assert.equal(path.status, 200)
  assert.equal(path.body.relPath, gen.body.relPath)
  // The path is rooted in THIS app's data dir — proving the API is the source of
  // truth, so a client never has to know (or guess) the data directory.
  assert.equal(path.body.absolutePath, join(dataDir, ...gen.body.relPath.split('/')))

  const missing = await api('GET', '/api/archive/nope/path')
  assert.equal(missing.status, 404)

  await api('DELETE', `/api/archive/${docId}`)
})

// ---- customer CRUD (must never disturb the invoice counter) -----------------
test('customer create / update / delete leave nextInvoiceSeq untouched', async () => {
  // Advance the counter first so we can prove customer writes don't rewind it.
  await api('POST', '/api/invoices', { customerId: 'c1', date: '2026-07-20', timesheetId: tsId, basis: 'day' })
  const seqBefore = (await api('GET', '/api/settings')).body.company.nextInvoiceSeq

  // create
  const created = await api('POST', '/api/customers', {
    id: 'cust-new',
    company: 'New Client BV',
    contactPerson: 'Ada',
    addressLines: ['Nieuwstraat 1'],
    vatNumber: 'BE0111.222.333',
    email: 'ada@new.be',
    defaultDayRate: 1200,
    defaultHourlyRate: 150,
    paymentTermsDays: 45,
    vatTreatment: 'reverse_charge_eu',
  })
  assert.equal(created.status, 200)
  assert.equal(created.body.company, 'New Client BV')
  const seqOf = async () => (await api('GET', '/api/settings')).body.company.nextInvoiceSeq
  const customersNow = async () => (await api('GET', '/api/customers')).body as any[]
  assert.ok((await customersNow()).some((c) => c.id === 'cust-new'))
  assert.equal(await seqOf(), seqBefore, 'create must not touch the counter')

  // update
  const updated = await api('PUT', '/api/customers/cust-new', { company: 'Renamed Client BV', defaultDayRate: 1300, vatTreatment: 'standard' })
  assert.equal(updated.status, 200)
  assert.equal(updated.body.company, 'Renamed Client BV')
  assert.equal(updated.body.defaultDayRate, 1300)
  assert.equal((await customersNow()).find((c) => c.id === 'cust-new').company, 'Renamed Client BV')
  assert.equal(await seqOf(), seqBefore, 'update must not touch the counter')

  // delete
  const del = await api('DELETE', '/api/customers/cust-new')
  assert.equal(del.status, 200)
  assert.ok(!(await customersNow()).some((c) => c.id === 'cust-new'))
  assert.equal(await seqOf(), seqBefore, 'delete must not touch the counter')
  // the original customer survives
  assert.ok((await customersNow()).some((c) => c.id === 'c1'))
})

// ---- invoice edit + identity lock -------------------------------------------
test('PUT /api/invoices edits fields but locks the legal identity', async () => {
  const created = await api('POST', '/api/invoices', { customerId: 'c1', date: '2026-08-01', timesheetId: tsId, basis: 'day' })
  const id = created.body.id
  const before = created.body

  const edited = await api('PUT', `/api/invoices/${id}`, {
    customerId: 'c1',
    date: '2026-08-20',
    dueDate: '2026-09-20',
    lines: [{ description: 'Edited advisory day', quantity: 2, unit: 'day', unitPrice: 1200 }],
    vatTreatment: 'exempt',
    standardVatRatePct: 21,
    reference: 'PO-EDIT',
    notes: 'edited',
    // tampering — must be ignored server-side:
    number: 'HACKED', seq: 999, structuredReference: '+++000/0000/00000+++', createdAt: '2000-01-01T00:00:00Z',
  })
  assert.equal(edited.status, 200)
  // editable fields changed
  assert.equal(edited.body.date, '2026-08-20')
  assert.equal(edited.body.vatTreatment, 'exempt')
  assert.equal(edited.body.reference, 'PO-EDIT')
  assert.equal(edited.body.lines[0].unitPrice, 1200)
  // identity locked
  assert.equal(edited.body.number, before.number)
  assert.equal(edited.body.seq, before.seq)
  assert.equal(edited.body.structuredReference, before.structuredReference)
  assert.equal(edited.body.createdAt, before.createdAt)

  const missing = await api('PUT', '/api/invoices/does-not-exist', { customerId: 'c1', date: '2026-08-20', dueDate: '2026-09-20', lines: [], vatTreatment: 'standard', standardVatRatePct: 21 })
  assert.equal(missing.status, 404)
})

// ---- regression: concurrent invoice creation never shares a number ----------
test('concurrent POST /api/invoices allocate distinct sequential numbers', async () => {
  await api('PUT', '/api/settings', SETTINGS(500)) // reset counter to a known base
  const N = 12
  const results = await Promise.all(
    Array.from({ length: N }, () =>
      api('POST', '/api/invoices', { customerId: 'c1', date: '2026-09-01', timesheetId: tsId, basis: 'day' }),
    ),
  )
  assert.ok(results.every((r) => r.status === 200))
  const numbers = results.map((r) => r.body.number)
  const seqs = results.map((r) => r.body.seq)
  assert.equal(new Set(numbers).size, N, `expected ${N} distinct numbers, got ${JSON.stringify(numbers)}`)
  assert.equal(new Set(seqs).size, N, 'expected distinct sequence numbers')
  // Contiguous 500..500+N-1, no gaps and no duplicates.
  assert.deepEqual([...seqs].sort((a, b) => a - b), Array.from({ length: N }, (_, i) => 500 + i))
  const settings = await api('GET', '/api/settings')
  assert.equal(settings.body.company.nextInvoiceSeq, 500 + N)
})

// ---- invoice delete cascades to its generated documents ---------------------
test('DELETE /api/invoices removes the invoice and its archive documents', async () => {
  await api('POST', '/api/documents', { kind: 'invoice', refId: invId1, format: 'pdf' })
  const beforeArchive = await api('GET', '/api/archive')
  assert.ok(beforeArchive.body.some((d: any) => d.refId === invId1))

  const del = await api('DELETE', `/api/invoices/${invId1}`)
  assert.equal(del.status, 200)

  const invoices = await api('GET', '/api/invoices')
  assert.ok(!invoices.body.some((i: any) => i.id === invId1))
  const afterArchive = await api('GET', '/api/archive')
  assert.ok(!afterArchive.body.some((d: any) => d.refId === invId1), 'archive docs for the invoice should be gone')
})
