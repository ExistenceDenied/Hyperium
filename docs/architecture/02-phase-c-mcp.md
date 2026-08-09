# Phase C — admin-finance as an MCP capability of hyperium-ai

## Problem

`hyperium-ai` agents should be able to *prepare* Belgian BV finance documents —
draft an invoice for a period, fill a timesheet, generate a PDF — as part of a
mission ("prepare July's invoice for Acme Bank"). `admin-finance` already does all
of this; we just need to let an agent drive it. Without breaking the one rule
that makes `admin-finance` safe.

## Goals

- An agent can **READ** finance state (customers, invoices, dashboards, archive).
- An agent can **PREPARE** drafts (customers, timesheets, invoices) and
  **GENERATE** PDF/Word documents, each held at hyperium-ai's approval gate.
- The data stays **local**; the agent gets back document *paths*, not money movement.

## Non-goals / hard invariant

- **No send, no pay, no transfer, no e-invoicing, no accounting-export.** These do
  not exist in `admin-finance` today (only three *unimplemented* interfaces:
  `EInvoiceSender`, `AccountingExporter`, `OcrService`). The MCP surface must never
  expose them even if someone implements them later.
- **No delete.** The `DELETE` routes are simply not wrapped.
- **No credentials.** `admin-finance` has none; the MCP server adds none.

The guarantee is **structural**: if a tool is never advertised in `tools/list`, no
prompt, model choice, or `--auto-approve` can invoke it. hyperium-ai's approval
gate is a human-in-the-loop control, *not* a capability firewall — so the firewall
lives in the server's tool list.

## Design

```
hyperium-ai agent
   │  stdio JSON-RPC (protocol 2024-11-05)
   ▼
admin-finance MCP server        apps/admin-finance/mcp/server.mjs
   │  HTTP (fetch)               plain Node ESM, no build step, clean stdout
   ▼
admin-finance REST API          Fastify @ 127.0.0.1:8930  (the single writer)
   │
   ▼
data/db.json + generated PDF/Word files   (local, git-ignored)
```

**Why an HTTP bridge and not in-process:** all the stateful logic (atomic invoice
numbering, generate→store→archive) lives behind the Fastify server, which owns a
*serialized write queue* over a single `db.json`. Routing every write through that
one process means **one writer, no race** — even while the web UI is open. An
in-process copy would become a second writer and could corrupt the counter.

**Why plain `.mjs` and not TypeScript:** the bridge only forwards JSON, so the
`@af/core` type-reuse payoff is marginal, and plain Node ESM launches with just
`node <path>` (node is on PATH) — no `tsx`, no build, and nothing but JSON-RPC on
stdout (a corrupted stdout stream would break the protocol).

### Tool surface (v1)

`readOnlyHint: true` → runs without approval. `readOnlyHint: false` → held at the
approval gate (mutates local state or writes a file). Nothing is destructive.

| Tool | Verb | Route | readOnly |
|------|------|-------|:--------:|
| `finance_get_settings` | READ | `GET /api/settings` | ✅ |
| `finance_list_customers` | READ | `GET /api/customers` | ✅ |
| `finance_get_customer` | READ | `GET /api/customers/:id` | ✅ |
| `finance_get_dashboard` | READ | `GET /api/dashboard/:key` | ✅ |
| `finance_list_invoices` | READ | `GET /api/invoices` | ✅ |
| `finance_get_invoice` | READ | `GET /api/invoices/:id` | ✅ |
| `finance_list_archive` | READ | `GET /api/archive` | ✅ |
| `finance_locate_document` | READ | (resolve archive relPath → abs path) | ✅ |
| `finance_get_or_create_timesheet` | PREPARE | `GET /api/timesheets/period/:key` | ❌ |
| `finance_set_timesheet_days` | PREPARE | `PUT /api/timesheets/:id` | ❌ |
| `finance_get_or_create_expense` | PREPARE | `GET /api/expenses/period/:key` | ❌ |
| `finance_set_expense` | PREPARE | `PUT /api/expenses/:id` | ❌ |
| `finance_upsert_customer` | PREPARE | `POST`/`PUT /api/customers` | ❌ |
| `finance_prepare_invoice` | PREPARE | `POST /api/invoices` | ❌ |
| `finance_update_invoice` | PREPARE | `PUT /api/invoices/:id` (identity locked server-side) | ❌ |
| `finance_generate_document` | GENERATE | `POST /api/documents` | ❌ |
| `finance_set_status` | WORKFLOW | `PATCH /api/<kind>/:id/meta` | ❌ |
| `finance_add_comment` | WORKFLOW | `PATCH /api/<kind>/:id/meta` | ❌ |
| `finance_download_document` | DELIVER | `GET /api/archive/:id/download` → writes to a folder | ❌ |

Deliberately **excluded**: every `DELETE`, `PUT /api/settings` (company config is
not agent scope), and anything resembling send/pay (none exists).

### Registration in hyperium-ai

Two paths, no client/runner code changes needed (transport + gating are generic):

1. **Ad-hoc:** config file `apps/hyperium-ai/examples/mcp/admin-finance.mcp.json`
   used via `hyperium do "…" --mcp examples/mcp/admin-finance.mcp.json`.
2. **First-class connector:** a `ConnectorPreset` added to
   `apps/hyperium-ai/infrastructure/connectors.py` `PRESETS`, so it shows up in the
   web connector wizard and persists to `workspace/.hyperium/connections.json`.
   Available to tasks when `HYPERIUM_TASK_CONNECTORS=1`.

Launch spec (both paths):
```json
{ "command": "node",
  "args": ["<repo>/apps/admin-finance/mcp/server.mjs"],
  "env": { "ADMIN_FINANCE_API": "http://127.0.0.1:8930" } }
```

### Runtime prerequisite

The bridge needs the admin-finance API running (`:8930`). The umbrella `start.bat`
already starts admin-finance; a finance mission simply requires it up. If the API
is unreachable the tools return a clear `isError` ("finance app not running").

## Alternatives considered

- **In-process `app.inject()`** — rejected: second writer → db race.
- **Import `@af/core` and reimplement persistence in the server** — rejected: throws
  away the tested Fastify persistence/generation and re-creates the race.
- **TypeScript + `tsx`** — rejected: build/launch friction and stdout-cleanliness
  risk for zero real benefit in a JSON forwarder.

## Rollout

1. Add `apps/admin-finance/mcp/server.mjs` (+ a README).
2. Add the hyperium-ai config file and the `connectors.py` preset.
3. Verify: start the API, drive the server over stdio (initialize → tools/list →
   a read tool → prepare an invoice → generate a PDF), confirm the file lands.
4. Document the `hyperium do --mcp` usage in the app READMEs.

## The invariant, restated

If any change to this surface would let an agent send an invoice, move money, pay,
or push financial data into the intelligence engine, it is out of scope — full stop.
