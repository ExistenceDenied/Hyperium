# admin-finance MCP server

`server.mjs` is the **agent-facing surface** of the Admin & Finance app: a small
stdio JSON-RPC (MCP, protocol `2024-11-05`) bridge that lets a `hyperium-ai` agent
**read, prepare and generate** finance documents by calling the running
admin-finance REST API.

It is **prepare-only, by construction**:

- it wraps no `DELETE` route,
- it exposes nothing that sends, pays, transfers, or e-invoices (the app has no
  such capability),
- it holds no credentials.

The safety guarantee is structural — a verb that is not in the `TOOLS` list cannot
be invoked by any prompt, model, or `--auto-approve` run. See
[`docs/architecture/02-phase-c-mcp.md`](../../../docs/architecture/02-phase-c-mcp.md).

## Run it

The bridge needs the Admin & Finance API up (default `http://127.0.0.1:8930`):

```bash
# 1. start the finance app (API on :8930)
cd apps/admin-finance && start-admin-finance.bat

# 2. from hyperium-ai, hand an agent the finance tools
cd apps/hyperium-ai
python main.py do "Prepare July's invoice for Acme Bank" \
  --mcp examples/mcp/admin-finance.mcp.json
```

Or enable the **Admin & Finance** connector in the web wizard (it's a preset in
`hyperium-ai/infrastructure/connectors.py`) and run tasks with
`HYPERIUM_TASK_CONNECTORS=1`.

## Config

| Env | Default | Meaning |
|-----|---------|---------|
| `ADMIN_FINANCE_API` | `http://127.0.0.1:8930` | Base URL of the running API |
| `ADMIN_FINANCE_DATA_DIR` | `../data` (next to this app) | Where generated files live, for resolving absolute paths |

## Tools

Read (no approval): `finance_get_settings`, `finance_list_customers`,
`finance_get_customer`, `finance_get_dashboard`, `finance_list_invoices`,
`finance_get_invoice`, `finance_list_archive`, `finance_locate_document`.

Prepare / generate (held at the approval gate): `finance_get_or_create_timesheet`,
`finance_set_timesheet_days`, `finance_upsert_customer`, `finance_prepare_invoice`,
`finance_update_invoice`, `finance_generate_document`.
