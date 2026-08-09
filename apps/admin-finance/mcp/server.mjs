#!/usr/bin/env node
// admin-finance MCP server — the agent-facing surface of the finance app.
//
// A thin stdio JSON-RPC (MCP, protocol 2024-11-05) bridge that lets a
// hyperium-ai agent READ / PREPARE / GENERATE finance documents by calling the
// running admin-finance REST API. It is intentionally *prepare-only*:
//   - it never wraps a DELETE route,
//   - it exposes nothing that sends, pays, transfers, or e-invoices
//     (the app has no such capability anyway),
//   - it holds no credentials.
// The safety guarantee is structural: a verb that is not in TOOLS cannot be
// invoked by any prompt, model, or --auto-approve run.
//
// Launch (by hyperium-ai): node apps/admin-finance/mcp/server.mjs
// Requires the admin-finance API running (default http://127.0.0.1:8930).

import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'
import { randomUUID } from 'node:crypto'

const PROTOCOL_VERSION = '2024-11-05'
const SERVER_INFO = { name: 'admin-finance', version: '0.1.0' }

const API = (process.env.ADMIN_FINANCE_API ?? 'http://127.0.0.1:8930').replace(/\/+$/, '')
const HERE = dirname(fileURLToPath(import.meta.url))
const DATA_DIR = process.env.ADMIN_FINANCE_DATA_DIR ?? resolve(HERE, '..', 'data')

// ---- stdio plumbing (stdout carries ONLY JSON-RPC; diagnostics go to stderr) ----
process.stdin.setEncoding('utf-8')
function send(message) {
  process.stdout.write(JSON.stringify(message) + '\n')
}
function reply(id, result) {
  send({ jsonrpc: '2.0', id, result })
}
function replyError(id, code, message) {
  send({ jsonrpc: '2.0', id, error: { code, message } })
}
function textResult(value, isError = false) {
  const text = typeof value === 'string' ? value : JSON.stringify(value, null, 2)
  return { content: [{ type: 'text', text }], ...(isError ? { isError: true } : {}) }
}

// ---- HTTP bridge to the admin-finance REST API ----
async function api(method, path, body) {
  let res
  try {
    res = await fetch(API + path, {
      method,
      headers: body !== undefined ? { 'content-type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (err) {
    throw new Error(
      `admin-finance API not reachable at ${API} (${err?.message ?? err}). ` +
        `Is the finance app running? Start it with apps/admin-finance/start-admin-finance.bat.`,
    )
  }
  const raw = await res.text()
  let parsed
  try {
    parsed = raw ? JSON.parse(raw) : null
  } catch {
    parsed = raw
  }
  if (!res.ok) {
    const detail = parsed && parsed.message ? parsed.message : raw
    throw new Error(`API ${method} ${path} → ${res.status}: ${detail}`)
  }
  return parsed
}

// ---- tool implementations ----
const handlers = {
  // ---------- READ ----------
  finance_get_settings: () => api('GET', '/api/settings'),
  finance_list_customers: () => api('GET', '/api/customers'),
  finance_get_customer: ({ id }) => api('GET', `/api/customers/${encodeURIComponent(id)}`),
  finance_get_dashboard: ({ period }) => api('GET', `/api/dashboard/${encodeURIComponent(period)}`),
  finance_list_invoices: () => api('GET', '/api/invoices'),
  finance_get_invoice: ({ id }) => api('GET', `/api/invoices/${encodeURIComponent(id)}`),
  finance_list_archive: () => api('GET', '/api/archive'),
  finance_locate_document: async ({ id }) => {
    const archive = await api('GET', '/api/archive')
    const doc = Array.isArray(archive) ? archive.find((d) => d.id === id) : null
    if (!doc) throw new Error(`No archived document with id ${id}.`)
    return {
      id: doc.id,
      title: doc.title,
      filename: doc.filename,
      relPath: doc.relPath,
      absolutePath: join(DATA_DIR, doc.relPath),
      sizeBytes: doc.sizeBytes,
    }
  },

  // ---------- PREPARE ----------
  finance_get_or_create_timesheet: ({ period }) =>
    api('GET', `/api/timesheets/period/${encodeURIComponent(period)}`),

  finance_set_timesheet_days: async ({ id, days, replace }) => {
    const current = await api('GET', `/api/timesheets/${encodeURIComponent(id)}`)
    let nextDays
    if (replace) {
      nextDays = days
    } else {
      // Merge by date: provided days upsert same-date entries; existing days on
      // other dates are preserved (so sending one day never wipes the rest).
      const byDate = new Map((current.days ?? []).map((d) => [d.date, d]))
      for (const d of days) byDate.set(d.date, d)
      nextDays = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date))
    }
    return api('PUT', `/api/timesheets/${encodeURIComponent(id)}`, { ...current, days: nextDays })
  },

  finance_get_or_create_expense: ({ period }) =>
    api('GET', `/api/expenses/period/${encodeURIComponent(period)}`),

  finance_set_expense: async ({ id, items, trips, mileageRatePerKm }) => {
    const current = await api('GET', `/api/expenses/${encodeURIComponent(id)}`)
    // Each item/trip needs an id (the web UI mints them client-side); default
    // an item's status to 'draft'. id is applied last so it always wins.
    const withIds = (arr, defaults) =>
      (arr ?? []).map((x) => ({ ...defaults, ...x, id: x.id || randomUUID() }))
    const next = { ...current }
    if (items !== undefined) next.items = withIds(items, { status: 'draft' })
    if (trips !== undefined) next.trips = withIds(trips, { roundTrip: false })
    if (mileageRatePerKm !== undefined) next.mileageRatePerKm = mileageRatePerKm
    return api('PUT', `/api/expenses/${encodeURIComponent(id)}`, next)
  },

  finance_upsert_customer: ({ id, ...customer }) => {
    // The API validates a full Customer (id included); the web UI mints the id
    // client-side, so we do the same when creating.
    const cid = id || randomUUID()
    return id
      ? api('PUT', `/api/customers/${encodeURIComponent(cid)}`, { ...customer, id: cid })
      : api('POST', '/api/customers', { ...customer, id: cid })
  },

  finance_prepare_invoice: (body) => api('POST', '/api/invoices', body),

  finance_update_invoice: async ({ id, ...changes }) => {
    const current = await api('GET', `/api/invoices/${encodeURIComponent(id)}`)
    // Legal-identity fields (number/seq/year/structuredReference/createdAt) are
    // re-locked server-side on PUT; sending them is harmless.
    return api('PUT', `/api/invoices/${encodeURIComponent(id)}`, { ...current, ...changes, id })
  },

  // ---------- GENERATE ----------
  finance_generate_document: async ({ kind, refId, format }) => {
    const doc = await api('POST', '/api/documents', { kind, refId, format })
    return { ...doc, absolutePath: join(DATA_DIR, doc.relPath) }
  },
}

// ---- tool catalog advertised to the agent ----
const readOnly = (title) => ({ title, readOnlyHint: true })
const writes = (title) => ({ title, readOnlyHint: false })
const obj = (properties, required = []) => ({ type: 'object', properties, required })
const S = { string: { type: 'string' }, number: { type: 'number' }, boolean: { type: 'boolean' } }

const TOOLS = [
  { name: 'finance_get_settings', description: 'Get company + financial settings (name, VAT number, invoice number format, rates).', inputSchema: obj({}), annotations: readOnly('Get settings') },
  { name: 'finance_list_customers', description: 'List all customers.', inputSchema: obj({}), annotations: readOnly('List customers') },
  { name: 'finance_get_customer', description: 'Get one customer by id.', inputSchema: obj({ id: S.string }, ['id']), annotations: readOnly('Get customer') },
  { name: 'finance_get_dashboard', description: 'Get the monthly dashboard (revenue, VAT collected/deductible, profit estimate) for a period. Pure read — creates nothing.', inputSchema: obj({ period: { ...S.string, description: 'Period key, YYYY-MM (e.g. 2026-07).' } }, ['period']), annotations: readOnly('Get monthly dashboard') },
  { name: 'finance_list_invoices', description: 'List all invoices (drafts and final).', inputSchema: obj({}), annotations: readOnly('List invoices') },
  { name: 'finance_get_invoice', description: 'Get one invoice by id.', inputSchema: obj({ id: S.string }, ['id']), annotations: readOnly('Get invoice') },
  { name: 'finance_list_archive', description: 'List generated documents (PDF/Word) with their metadata.', inputSchema: obj({}), annotations: readOnly('List archive') },
  { name: 'finance_locate_document', description: 'Resolve the absolute local file path of an archived generated document by id.', inputSchema: obj({ id: S.string }, ['id']), annotations: readOnly('Locate document') },

  { name: 'finance_get_or_create_timesheet', description: 'Get the timesheet for a period (YYYY-MM), creating a blank draft if none exists. Returns the timesheet including its id.', inputSchema: obj({ period: { ...S.string, description: 'Period key, YYYY-MM.' } }, ['period']), annotations: writes('Get or create timesheet') },
  { name: 'finance_set_timesheet_days', description: 'Add or update days on a timesheet. By default merges by date (provided days upsert same-date entries; other existing days are kept). Pass replace=true to overwrite the whole days list instead. Each day: {date (YYYY-MM-DD), billable (bool), hours (number), customerId?, project?, comment?}.', inputSchema: obj({ id: S.string, days: { type: 'array', items: obj({ date: S.string, billable: S.boolean, hours: S.number, customerId: S.string, project: S.string, comment: S.string }, ['date', 'billable', 'hours']) }, replace: { ...S.boolean, description: 'If true, replace all days instead of merging by date. Default false.' } }, ['id', 'days']), annotations: writes('Set timesheet days') },
  { name: 'finance_get_or_create_expense', description: 'Get the expense note for a period (YYYY-MM), creating a blank draft if none exists. Returns it including its id.', inputSchema: obj({ period: { ...S.string, description: 'Period key, YYYY-MM.' } }, ['period']), annotations: writes('Get or create expense note') },
  { name: 'finance_set_expense', description: 'Set the items and/or mileage trips on an expense note. Replaces each array you provide; omit an array to keep it. Item: {date (YYYY-MM-DD), category, description, supplier, amount, vatAmount, status?}. Trip: {date, departure, destination, purpose, distanceKm, roundTrip?, customerId?}.', inputSchema: obj({ id: S.string, items: { type: 'array', items: obj({ date: S.string, category: S.string, description: S.string, supplier: S.string, amount: S.number, vatAmount: S.number, status: { ...S.string, enum: ['draft', 'submitted', 'reimbursed'] } }, ['date', 'category', 'description', 'supplier', 'amount', 'vatAmount']) }, trips: { type: 'array', items: obj({ date: S.string, departure: S.string, destination: S.string, purpose: S.string, distanceKm: S.number, roundTrip: S.boolean, customerId: S.string }, ['date', 'departure', 'destination', 'purpose', 'distanceKm']) }, mileageRatePerKm: S.number }, ['id']), annotations: writes('Set expense items/trips') },
  { name: 'finance_upsert_customer', description: 'Create a customer (omit id) or update one (provide id). Fields: company, contactPerson?, addressLines[], vatNumber?, email?, defaultDayRate, defaultHourlyRate, paymentTermsDays, vatTreatment.', inputSchema: obj({ id: S.string, company: S.string, contactPerson: S.string, addressLines: { type: 'array', items: S.string }, vatNumber: S.string, email: S.string, defaultDayRate: S.number, defaultHourlyRate: S.number, paymentTermsDays: S.number, vatTreatment: { ...S.string, enum: ['standard', 'reverse_charge_eu', 'exempt', 'zero'] } }, ['company']), annotations: writes('Create/update customer') },
  { name: 'finance_prepare_invoice', description: 'Prepare a DRAFT invoice. Bill a timesheet by day/hour (give timesheetId + basis) and/or add extraLines. Assigns a legal invoice number + Belgian structured reference but sends nothing.', inputSchema: obj({ customerId: S.string, date: { ...S.string, description: 'Invoice date YYYY-MM-DD.' }, timesheetId: S.string, basis: { ...S.string, enum: ['day', 'hour'] }, vatTreatment: { ...S.string, enum: ['standard', 'reverse_charge_eu', 'exempt', 'zero'] }, paymentTermsDays: S.number, reference: S.string, notes: S.string, extraLines: { type: 'array', items: obj({ description: S.string, quantity: S.number, unit: S.string, unitPrice: S.number }, ['description', 'quantity', 'unit', 'unitPrice']) } }, ['customerId', 'date']), annotations: writes('Prepare draft invoice') },
  { name: 'finance_update_invoice', description: 'Update fields on an existing invoice draft (e.g. lines, notes, dueDate). Legal identity (number/seq/year/reference) is locked server-side and cannot change.', inputSchema: obj({ id: S.string, notes: S.string, reference: S.string, dueDate: S.string, lines: { type: 'array', items: obj({ description: S.string, quantity: S.number, unit: S.string, unitPrice: S.number }, ['description', 'quantity', 'unit', 'unitPrice']) } }, ['id']), annotations: writes('Update invoice draft') },

  { name: 'finance_generate_document', description: 'Generate a PDF or Word document from a timesheet/invoice/expense. Writes a versioned file into the local archive and returns its metadata + absolute path.', inputSchema: obj({ kind: { ...S.string, enum: ['timesheet', 'invoice', 'expense'] }, refId: { ...S.string, description: 'Id of the timesheet/invoice/expense.' }, format: { ...S.string, enum: ['pdf', 'docx'] } }, ['kind', 'refId', 'format']), annotations: writes('Generate document') },
]

// ---- JSON-RPC dispatch ----
async function handleCall(id, params) {
  const name = params?.name
  const args = params?.arguments ?? {}
  const fn = handlers[name]
  if (!fn) return replyError(id, -32602, `Unknown tool: ${name}`)
  try {
    const value = await fn(args)
    reply(id, textResult(value))
  } catch (err) {
    reply(id, textResult(`Error: ${err?.message ?? err}`, true))
  }
}

async function dispatch(msg) {
  const { id, method, params } = msg
  switch (method) {
    case 'initialize':
      return reply(id, {
        protocolVersion: PROTOCOL_VERSION,
        capabilities: { tools: {} },
        serverInfo: SERVER_INFO,
      })
    case 'notifications/initialized':
      return // notification, no reply
    case 'tools/list':
      return reply(id, { tools: TOOLS })
    case 'tools/call':
      return handleCall(id, params)
    case 'ping':
      return reply(id, {})
    default:
      if (id !== undefined) replyError(id, -32601, `Unknown method: ${method}`)
  }
}

// ---- line-buffered stdin loop ----
let buffer = ''
process.stdin.on('data', (chunk) => {
  buffer += chunk
  let nl
  while ((nl = buffer.indexOf('\n')) >= 0) {
    const line = buffer.slice(0, nl).trim()
    buffer = buffer.slice(nl + 1)
    if (!line) continue
    let msg
    try {
      msg = JSON.parse(line)
    } catch {
      continue // ignore non-JSON noise
    }
    dispatch(msg)
  }
})
process.stdin.on('end', () => process.exit(0))
