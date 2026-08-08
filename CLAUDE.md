# Hyperium master application — repo memory

Umbrella monorepo for Hyperium's applications. Owner: K. Leunis. Each app under
`apps/` keeps its own language, runtime, tests and git history.

## Layout

```
hyperium/
├── apps/
│   ├── hyperium-ai/      Python AI consultancy OS (Ollama/Claude, MCP, agents)
│   └── admin-finance/    TypeScript BV finance app (Fastify + React/Vite)
├── docs/architecture/    monorepo rationale + the A→C roadmap
├── start.bat             unified launcher (picks an app)
└── README.md
```

Each app is self-contained. There is **no shared runtime yet** — this is phase A.
Work inside an app using that app's own conventions; its own `CLAUDE.md` /
`README.md` (where present) is authoritative for its internals.

## The rules that are not negotiable

1. **Public sources only** in the knowledge base and any published asset. Client
   or Projective-confidential material never enters an intelligence engine; it is
   sanitised at engagement closeout, owner-reviewed, no exceptions.
2. **Client-facing content is capped at L1, permanently** — the owner reviews and
   approves every client-bound draft. Blast radius, not reliability, sets the ceiling.
3. **`admin-finance` stays isolated.** It has no AI, no external integrations, no
   credentials, and never moves money — it only prepares → owner reviews →
   generates → downloads. Financial data stays local and never enters the
   intelligence engine. **Phase C (exposing it to `hyperium-ai` as an MCP
   capability) must preserve this**: an agent may *prepare* a document, but the
   data stays local and the agent never sends, pays, or transfers anything.

## Working notes

- Reading Office files (`.pptx`/`.docx`) with python can hit a OneDrive
  `PermissionError` — copy to a temp dir first, then read. (This umbrella lives
  outside OneDrive at `C:\AI\hyperium`, which avoids most such locks.)
- Both apps persist to local JSON + generated files, git-ignored per app
  (`apps/*/data`, `apps/*/workspace`, `logs`). Never commit runtime/financial data.
- Subtree remotes for pulling upstream fixes: `hyperium-ai-src`, `admin-finance-src`.
