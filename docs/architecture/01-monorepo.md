# Monorepo architecture — the A → C roadmap

## Why a monorepo (and not a code merge)

`hyperium-ai` (Python) and `admin-finance` (TypeScript) do not share a language
or runtime, so they cannot become one shared codebase without a full rewrite of
one side — throwing away ~16k lines of working Python or a complete, tested TS
app. We don't do that.

Instead they become **one application at the repository and launcher level**:
two self-contained apps under `apps/`, one umbrella launcher, one set of shared
docs and rules, full git history preserved for each (added via `git subtree`).

Both apps happen to follow the same clean/hexagonal design (a pure `core`, ports
pointing outward), which makes them cleanly composable at the edges later —
without reaching into each other's internals.

## Phase A — umbrella repo  *(current)*

```
hyperium/
├── apps/
│   ├── hyperium-ai/      subtree of Hyperium-Studios/Hyperium @ feature/agentic-tasks
│   └── admin-finance/    subtree of ExistenceDenied/hyperium-admin-finance @ main
├── docs/architecture/    this file
├── start.bat             menu launcher
├── CLAUDE.md             carried-over non-negotiable rules
└── README.md
```

- Each app keeps its own dependencies, local data dir, config and ports.
- Nothing is shared at runtime. The apps do not know about each other.
- **Pulling upstream fixes** into an app after this point:
  ```bash
  git fetch admin-finance-src
  git subtree pull --prefix=apps/admin-finance admin-finance-src main
  ```
  (and `hyperium-ai-src` / `feature/agentic-tasks` for the other).

### Runtime data

Both apps persist to local JSON + generated files that are **git-ignored**
(`apps/*/data`, `apps/*/workspace`, `logs`). That data is not carried by subtree
(it was never tracked). It was copied over from the original working copies so
the apps keep their existing state, and it stays local — never committed. This
is what keeps `admin-finance`'s financial records out of any published asset.

## Phase B — optional shared shell  *(skip unless wanted)*

A single portal / reverse-proxy fronting both web UIs under one nav. Cosmetic;
still two backends. Only worth doing if a unified front door is desired.

## Phase C — admin-finance as an MCP capability of hyperium-ai  *(next real step)*

`hyperium-ai` already has a from-scratch MCP client and a tool/port abstraction
(`infrastructure/mcp/`, `infrastructure/tools/`). `admin-finance` already has a
clean REST API (Fastify, `server/src/routes.ts`) over a pure domain `core`.

The plan:

1. Wrap `admin-finance`'s domain/API as an **MCP server** (a thin adapter that
   exposes read + *prepare* operations: list customers, draft an invoice for a
   period, generate a timesheet — the same things the REST API already does).
2. Register that MCP server as a **connector/tool** in `hyperium-ai`, so an agent
   can be handed a mission like "prepare July's invoice for Acme Bank" and drive
   `admin-finance` to produce the draft document.
3. **Preserve the guardrail** end to end: the MCP surface exposes only
   *prepare/generate/download*. No send, no pay, no transfer, no credentials.
   The owner still reviews and sends manually. Financial data never leaves the
   local machine and never enters any published/intelligence asset.

### The one hard invariant

Whatever phase C looks like in code, the `admin-finance` isolation rule wins over
convenience. If a proposed integration would let an agent send an invoice, move
money, or push financial data into the engine, it is out of scope — full stop.
