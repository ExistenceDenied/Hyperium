# Hyperium BV — Admin & Finance

A local web app that **prepares** Hyperium BV's monthly financial administration:
timesheets, invoices, and expense notes (with Belgian forfaitary mileage), a monthly
dashboard, a document archive, and settings.

> **Guardrail (capability 06 charter).** This app only ever *prepares → reviews →
> generates → downloads* documents. It never moves money, never auto-sends an invoice,
> and never handles credentials or payment details. The owner reviews and sends.
> Financial data stays **local** and out of the intelligence engine's public assets.

## Run it

Double-click **`start-admin-finance.bat`** (Windows). First run installs dependencies,
then it starts the API + web app and opens <http://localhost:5173>.

Manually:

```bash
npm install        # once
npm run dev        # Fastify API (:8930) + Vite web (:5173)
npm run typecheck  # strict tsc across all three packages
npm test           # regression suite (core domain + server API)
```

## Tests (regression / NRT suite)

`npm test` runs the non-regression suite on Node's built-in test runner via `tsx`
(no extra dependency, no build step):

- **`core/test/`** — pure domain maths: rounding, VAT, mileage (round-trip
  doubling), the mod-97 structured reference, invoice/timesheet/expense totals,
  the invoice builder, dashboard aggregation, invoice-number tokens.
- **`server/test/`** — the REST API driven in-process via Fastify `app.inject()`:
  settings, timesheet/expense/invoice/archive CRUD, document generation,
  dashboard, 404s, invoice-edit **identity lock** (number/sequence/structured
  reference never change on edit), and a **concurrency regression** proving
  simultaneous invoice creation always allocates distinct, contiguous numbers.

The server suite writes to a throwaway temp directory (via the `AF_DATA_DIR`
override), so it never touches `data/db.json`. Run one package with
`npm run test -w @af/core` or `npm run test -w @af/server`.

Data is written under **`admin-finance/data/`**:
`db.json` (entities) and `invoices/ timesheets/ expenses/` (generated PDF/Word, versioned).
Back this folder up — it *is* the records. It is deliberately git-ignored.

## Architecture (clean, layered — business logic never lives in React)

```
core/     Pure domain + application. No framework. Strict TS + zod + date-fns.
          domain/       money · vat · mileage · structured-reference · period ·
                        entities (zod schemas) · calculators (totals, invoice builder,
                        dashboard aggregates)
          application/  ports.ts — repository + DocumentGenerator + DocumentStore
                        interfaces, plus future-integration ports.
server/   Infrastructure + REST. Fastify. Implements the core ports:
          infra/        db (JSON store) · repositories · documentStore (fs) ·
                        pdf (pdfmake) · word (docx)
          app/          documents.ts — generate → store → archive orchestration
          routes.ts     the REST API
web/      UI only. React + Vite + Tailwind + React Router. Thin: calls the API,
          imports `core` for instant on-screen calculations.
          pages/        Dashboard · Timesheet · Invoices · Expenses · Archive · Settings
```

The dependency rule points inward: `web → server → core`, and `core` depends on nothing.
All money maths (VAT, mileage, invoice totals, the mod-97 structured reference) lives in
`core` and is unit-testable without a browser or a server.

## House typeface

Documents are set in **IBM Plex** (SIL OFL) — Plex Serif for the wordmark and titles,
Plex Sans for everything else. **Both formats embed the fonts**, so they render
identically on any machine with nothing installed:

- **PDF** — pdfkit subsets and embeds the faces.
- **Word** — the used faces are embedded per the OOXML obfuscated-font scheme
  (`word/fonts/*.odttf` + `fontTable.xml`, `<w:embedTrueTypeFonts/>`), so `.docx`
  files carry the type (~370 KB each). Implemented in `server/src/infra/embedFonts.ts`.

Font files and licence live in `server/assets/fonts/` (`OFL.txt`).

## Belgian specifics (all configurable in Settings)

- **VAT** default 21 %, with per-customer treatment: standard, intra-EU **reverse charge**
  (prints the art. 21 §2 / art. 196 legal mention), exempt, zero-rated.
- **Structured payment reference** — `+++xxx/xxxx/xxxxx+++` with the mod-97 check.
- **Mileage** — forfaitary €/km rate (seed value `0.4415`, **verify the current official
  rate**); round trips count double; monthly km + reimbursement totals.
- **Invoice numbering** — format string with `{year}`, `{seq}`, `{seq:3}` tokens.

## Extending it (designed-in — each item is a new adapter, not a rewrite)

Everything sits behind ports in `core/application/ports.ts`:

| Future capability | Extension point |
|---|---|
| Accounting export (Exact / Yuki / Odoo) | implement `AccountingExporter` |
| PEPPOL e-invoicing | implement `EInvoiceSender` |
| OCR receipts | implement `OcrService` |
| Bank reconciliation, VAT declarations, annual accounts, corporate tax | new application modules over the same repositories |
| Swap file storage for a database | new `*Repository` + `DocumentStore` implementations; `core` unchanged |

## API (all under `/api`)

`GET/PUT /settings` (company + financial only) ·
`GET /customers`, `POST /customers`, `GET/PUT/DELETE /customers/:id` (a top-level
collection, referenced by invoices/timesheets/expenses — not part of settings) ·
`GET /timesheets`, `GET /timesheets/period/:key`, `PUT /timesheets/:id` ·
`GET /invoices`, `POST /invoices`, `GET/PUT /invoices/:id` · `GET /expenses/period/:key`,
`PUT /expenses/:id` · `GET /dashboard/:key` · `GET /archive`, `POST /documents`,
`PATCH /archive/:id`, `GET /archive/:id/download`.
