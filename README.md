# Hyperium — master application

One umbrella repository for Hyperium's applications. Each app keeps its own
language, runtime, tests and full git history, but now lives, versions and
launches from a single place.

## Apps

| Path | What it is | Stack | Runs on |
|------|------------|-------|---------|
| [`apps/hyperium-ai`](apps/hyperium-ai) | AI consultancy OS — turns natural-language *missions* into Word/PPT/Excel/email deliverables via methodology-driven, capability-matched agents | Python 3.11, Ollama/Claude, MCP | `:8765` (web) + CLI |
| [`apps/admin-finance`](apps/admin-finance) | Belgian BV finance/admin — timesheets, VAT-correct invoices, expense/mileage notes → PDF/Word | TypeScript, Fastify + React/Vite | API `:8930`, web `:5173` |

## Quick start

Double-click **`start.bat`** and pick an app, or run one directly:

```bash
# AI OS (from its own folder)
cd apps/hyperium-ai && start.bat

# Finance app (from its own folder)
cd apps/admin-finance && start-admin-finance.bat
```

`start.bat` also has a **Both** option — start the finance API and the AI OS
together, which phase C's agent-driven finance tools need.

Each app is self-contained: its own dependencies, its own local data directory,
its own config. Nothing is shared at runtime yet — this is **phase A** (see
[the roadmap](docs/architecture/01-monorepo.md)).

## Testing

Run both suites from the root (mirrors CI):

```bash
pwsh ./test-all.ps1
```

CI runs the same on every push/PR to `main`
([.github/workflows/ci.yml](.github/workflows/ci.yml)), on `windows-latest`.

## The non-negotiable rules

These carry over from the firm's operating model and **bind every app in this
repo**. See [`CLAUDE.md`](CLAUDE.md) for the full text.

1. **Public sources only** in any published asset.
2. **Client-facing content is capped at L1** — owner reviews every client-bound draft.
3. **`admin-finance` stays isolated** — no AI, no external calls, no credentials,
   never moves money. Financial data never enters the intelligence engine.
   Any future integration (phase C) must preserve this.

## Where this is going

- **Phase A (done):** umbrella repo — both apps side by side, one launcher, one
  set of docs, full history preserved.
- **Phase C (later):** expose `admin-finance` to `hyperium-ai` as an MCP
  capability, so an agent can *prepare* finance documents — while the data stays
  local and the agent never sends or pays anything.

See [`docs/architecture/01-monorepo.md`](docs/architecture/01-monorepo.md).
