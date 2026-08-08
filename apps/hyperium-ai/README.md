# Hyperium

An AI consultancy that runs on your own machine. Give it a mission — "a full-day
BA training pack", "a quote for a bathroom refit", "a two-week social campaign" —
and capability-matched agents plan it, do the work, review their own quality and
iterate, and hand you the deliverables as **Word, PowerPoint, Excel or email**.

Everything runs locally on [Ollama](https://ollama.com); nothing leaves your
computer, and there is no per-use cost.

## Quick start (Windows)

1. Install [Python 3.11+](https://www.python.org/downloads/) (tick *Add to PATH*).
2. Right-click **`install.ps1`** → *Run with PowerShell*. It installs Hyperium,
   sets up [Ollama](https://ollama.com), and downloads the local model.
3. Double-click **`start.bat`**. Your browser opens the interface at
   `http://127.0.0.1:8765`.

## What you can do

**From the browser** (`start.bat`, or `hyperium serve`):
- **Tasks** — give the agent a one-off job; it works and reports back, asking
  before it changes anything.
- **Backlog** — capture missions; launch them into engagements.
- **Engagements** — review deliverables, approve or send back with feedback.

**From the command line:**

```bash
# a one-off task (reads files/web; asks before it writes)
hyperium do "Summarise the reviews in reviews.txt and draft three replies"

# run a whole engagement, reviewed and iterated with no human in the loop,
# then export it as the file types a client receives
hyperium run "Quote: bathroom refit" "Full bathroom, ~£6k, 5 days, supply & fit" \
    --methodology customer-proposal --autonomous
hyperium export <engagement-id>          # -> proposal.docx

hyperium tools        # what the agent can reach
hyperium task list    # every task it has run
```

## Methodologies included

`business-analysis` · `solution-delivery` · `process-improvement` ·
`training-design` · `customer-proposal` · `marketing-pack`

Add your own by dropping a JSON file in `methodologies/` and a matching template
in `templates/`. Tune any agent's style by editing its file in
`core/execution/prompting/capabilities/`.

## Choosing a model

Hyperium runs on whatever Ollama model you point it at (`HYPERIUM_MODEL`), and it
uses your GPU automatically. The default is **`qwen3:latest`** (an 8B model that
runs fully on an 8 GB graphics card — the fast, reliable choice). Larger models
(`qwen3:14b`, `qwen3:30b-a3b`) spill onto the CPU and slow down. Use whatever you
have pulled — check with `ollama list`. For the autonomous reviewer you can set a
separate, sharper model with `HYPERIUM_REVIEW_MODEL`.

## Architecture

See [`docs/architecture/`](docs/architecture/) — a mission is planned by a
methodology (not the model), executed by capability-matched agents, and held at
quality gates with human (or autonomous) approval. The design invariants are
enforced by tests (`tests/test_architecture.py`).
