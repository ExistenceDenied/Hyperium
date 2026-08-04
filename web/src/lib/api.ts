import type {
  BillingBasis,
  Comment,
  Customer,
  DashboardData,
  DocStatus,
  ExpenseNote,
  GeneratedDocument,
  Invoice,
  InvoiceLine,
  Settings,
  Timesheet,
  VatTreatment,
} from '@af/core'

export type DeliverableKind = 'timesheet' | 'invoice' | 'expense'
const PLURAL: Record<DeliverableKind, string> = { timesheet: 'timesheets', invoice: 'invoices', expense: 'expenses' }

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  // Only advertise a JSON body when we actually send one — otherwise Fastify
  // rejects bodyless requests (DELETE) with FST_ERR_CTP_EMPTY_JSON_BODY.
  const headers: Record<string, string> = { ...(init?.headers as Record<string, string> | undefined) }
  if (init?.body != null) headers['Content-Type'] = 'application/json'
  const res = await fetch(`/api${path}`, { ...init, headers })
  if (!res.ok) throw new Error(`${res.status} — ${await res.text()}`)
  return (await res.json()) as T
}

export interface CreateInvoiceInput {
  customerId: string
  date: string
  timesheetId?: string
  basis?: BillingBasis
  vatTreatment?: VatTreatment
  paymentTermsDays?: number
  reference?: string
  extraLines?: InvoiceLine[]
  notes?: string
}

/** Editable fields of an existing invoice. Identity fields are fixed server-side. */
export interface UpdateInvoiceInput {
  customerId: string
  date: string
  dueDate: string
  lines: InvoiceLine[]
  vatTreatment: VatTreatment
  standardVatRatePct: number
  reference?: string
  notes?: string
}

export const api = {
  getSettings: () => req<Settings>('/settings'),
  saveSettings: (s: Settings) => req<Settings>('/settings', { method: 'PUT', body: JSON.stringify(s) }),

  // Customer CRUD — touches only settings.customers (leaves the invoice counter alone).
  createCustomer: (c: Customer) => req<Customer>('/customers', { method: 'POST', body: JSON.stringify(c) }),
  updateCustomer: (c: Customer) => req<Customer>(`/customers/${c.id}`, { method: 'PUT', body: JSON.stringify(c) }),
  deleteCustomer: (id: string) => req<{ ok: boolean }>(`/customers/${id}`, { method: 'DELETE' }),

  listTimesheets: () => req<Timesheet[]>('/timesheets'),
  timesheetForPeriod: (key: string) => req<Timesheet>(`/timesheets/period/${key}`),
  saveTimesheet: (t: Timesheet) => req<Timesheet>(`/timesheets/${t.id}`, { method: 'PUT', body: JSON.stringify(t) }),

  listInvoices: () => req<Invoice[]>('/invoices'),
  getInvoice: (id: string) => req<Invoice>(`/invoices/${id}`),
  createInvoice: (body: CreateInvoiceInput) => req<Invoice>('/invoices', { method: 'POST', body: JSON.stringify(body) }),
  // Edit an existing invoice. Legal-identity fields (number, seq, year,
  // structured reference) are preserved server-side and ignored if sent.
  updateInvoice: (id: string, body: UpdateInvoiceInput) =>
    req<Invoice>(`/invoices/${id}`, { method: 'PUT', body: JSON.stringify(body) }),

  listExpenses: () => req<ExpenseNote[]>('/expenses'),
  expenseForPeriod: (key: string) => req<ExpenseNote>(`/expenses/period/${key}`),
  saveExpense: (e: ExpenseNote) => req<ExpenseNote>(`/expenses/${e.id}`, { method: 'PUT', body: JSON.stringify(e) }),

  dashboard: (key: string) => req<DashboardData>(`/dashboard/${key}`),

  updateMeta: (kind: DeliverableKind, id: string, meta: { status?: DocStatus; comments?: Comment[] }) =>
    req<unknown>(`/${PLURAL[kind]}/${id}/meta`, { method: 'PATCH', body: JSON.stringify(meta) }),
  deleteDoc: (kind: DeliverableKind, id: string) => req<{ ok: boolean }>(`/${PLURAL[kind]}/${id}`, { method: 'DELETE' }),
  deleteArchive: (id: string) => req<{ ok: boolean }>(`/archive/${id}`, { method: 'DELETE' }),

  listArchive: () => req<GeneratedDocument[]>('/archive'),
  renameArchive: (id: string, title: string) =>
    req<GeneratedDocument>(`/archive/${id}`, { method: 'PATCH', body: JSON.stringify({ title }) }),
  generate: (kind: 'timesheet' | 'invoice' | 'expense', refId: string, format: 'pdf' | 'docx') =>
    req<GeneratedDocument>('/documents', { method: 'POST', body: JSON.stringify({ kind, refId, format }) }),
  downloadUrl: (id: string, filename?: string) =>
    `/api/archive/${id}/download${filename ? `/${encodeURIComponent(filename)}` : ''}`,
}
