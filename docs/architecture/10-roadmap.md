# Hyperium Roadmap

> Version: 2.0
> Status: **CANONICAL** — this is the single roadmap for Hyperium.
> Status of every item below was verified against the source tree and a live
> end-to-end run, not from memory.

---

# Purpose

This document describes the evolution of Hyperium and **what has actually been
delivered**.

Every feature carries a status. A feature is only ✅ Delivered when it runs in
the product and is covered by a test — not when a class for it exists.

| Symbol | Meaning |
|---|---|
| ✅ | Delivered — works end to end and is tested |
| 🟡 | Partial — usable, with a stated limitation |
| ⬜ | Not started |

---

# Where we are

**1.0 complete (28 / 28). 1.5 complete (10 / 10). 2.0 is 75% delivered (6 / 8).**

An engagement runs end to end: a mission is captured in a backlog, analysed
into a dependency-ordered plan, executed by capability-matched resources,
assembled into a versioned deliverable, and held at a human approval gate that
survives process exit. Rejection sends it back for rework with the reviewer's
feedback. Humans can execute activities assigned to them and hand the work
back. Deliverables are reviewed in a browser, with a diff between versions.

The one thing to be clear about: **both ordering and plan content are now
deterministic.** A methodology — authored as data, validated on load — decides
what work an engagement contains and when it runs; the model writes the content
of each activity and nothing else. Three methodologies and fourteen techniques
ship with the platform, and stages are governed by checkable quality gates.

That was the whole of 2.0, and it is what separates Hyperium from a prompt
chain. What remains in 2.0 is output format and provider breadth, not the
thesis.

Vocabulary follows [ADR-001](ADR-001-mission-driven-architecture.md),
[ADR-003](ADR-003-capability-based-execution.md) and
[ADR-004](ADR-004-execution-model.md): a **Mission** is the highest-level
business concept, a **Project** is the execution vehicle created from it, an
**Activity** is the atomic unit of work, and work is assigned to
**Capabilities** provided by **Resources** — never to agents.

---

# Hyperium 1.0 — Execute one mission end to end

**Status: ✅ Delivered — 28 / 28 features**

## Mission management

| Feature | Status | Where it lives |
|---|---|---|
| Mission model — objective, criteria, constraints, stakeholders | ✅ | `core/missions/` |
| Mission backlog with full CRUD | ✅ | `application/missions/mission_backlog_service.py` |
| Backlog priority and lifecycle (draft → ready → launched → archived) | ✅ | `core/missions/mission_status.py` |
| Validation deferred to launch, so drafts may be incomplete | ✅ | `MissionValidator`, enforced in `launch()` |
| Mission analysis producing summary, assumptions and risks | ✅ | `core/analysis/` — since 2.0 it no longer plans the work |

## Planning and execution

| Feature | Status | Where it lives |
|---|---|---|
| Capability-based allocation: Activity → Capability → Resource | ✅ | `application/execution/capability_matcher.py` |
| Activity dependency graph with topological ordering | ✅ | `core/planning/dependency_graph.py` |
| Cyclic / unsatisfiable plans rejected, not guessed at | ✅ | `CircularDependencyError`, `UnknownDependencyError` |
| Real content generation by capability prompt strategy | ✅ | `core/execution/prompting/` |
| Upstream output fed into downstream activities | ✅ | `ActivityPromptBuilder` |
| Human and tool resources modelled and allocated | ✅ | `HumanResource`, `ToolResource`, `ExternalServiceResource` |
| Humans submit work assigned to them | ✅ | `ProjectService.submit_work`, `hyperium submit` |

## Deliverables and review

| Feature | Status | Where it lives |
|---|---|---|
| Deliverable content assembled from activity output | ✅ | `ExecutionEngine._assemble` |
| Immutable versioning — a revision never overwrites its predecessor | ✅ | `Deliverable.add_version` |
| Blocking human approval gate | ✅ | `ExecutionPlan.is_ready`, `DeliverableStatus` |
| Rework loop — rejection regenerates with reviewer feedback | ✅ | `Deliverable.request_changes` |
| Warning when a revision makes downstream work stale | ✅ | `ExecutionEngine._warn_about_stale_downstream` |

## Platform

| Feature | Status | Where it lives |
|---|---|---|
| Project and plan persistence; stop and resume across processes | ✅ | `infrastructure/persistence/` |
| Workspace as the store of produced artifacts | ✅ | `ArtifactStore` / `FileArtifactStore` |
| Command line interface for the full lifecycle | ✅ | `interfaces/cli.py` |
| Configuration through `HYPERIUM_*` environment variables | ✅ | `config/settings.py` |
| Logging to file and stream | ✅ | `infrastructure/observability/` — plain text; correlation by mission/activity is 4.0 |
| Retry with exponential backoff on provider failure | ✅ | `infrastructure/llm/resilient_provider.py` |
| Call timeouts | ✅ | `OllamaProvider(timeout_seconds=…)`, `HYPERIUM_LLM_TIMEOUT` |
| Retirement of the legacy agent/runtime stack | ✅ | Deleted under [ADR-004](ADR-004-execution-model.md) |
| Schema migrations — an older engagement still opens | ✅ | `infrastructure/persistence/migrations.py` |
| Architecture invariants enforced by tests | ✅ | `tests/test_architecture.py` |
| CI: lint, tests, methodology validation | ✅ | `.github/workflows/ci.yml` |

## Success criteria

| Criterion | Met |
|---|---|
| A mission runs end to end without intervention between activities | ✅ |
| Activities execute in dependency order; a cyclic plan is rejected | ✅ |
| Every deliverable revision is a retrievable version | ✅ |
| Reliable review loops, including a blocking human approval step | ✅ |
| A project can be stopped and resumed without losing state | ✅ |
| No execution path depends on `AgentRegistry` or `WorkItem` | ✅ |

## Known limitations carried forward

These are real, and each is tracked in a later release rather than left
implicit:

- Activities execute **sequentially**. The dependency graph expresses safe
  parallelism; the engine does not use it yet → **4.0**.
- **One LLM provider.** The abstraction exists but only Ollama implements it
  → still open in **2.0**.
- Logs are not correlated to a mission or activity, and there is no audit trail
  of approvals → **4.0**.
- The allocator has **no capacity model** — one resource can be assigned every
  activity → **4.0**.
- `isinstance(resource, AIResource)` at four sites decides who may execute; a
  new resource type requires editing the engine → **4.0**.
- The capability catalogue is hardcoded Python, so a methodology needing a
  ninth capability still requires a code change → **2.0**.

---

# Hyperium 1.5 — A usable human loop

**Status: ✅ Delivered — 10 / 10 features**

## Goal

Make review something a person actually wants to do. The approval gate landed
in 1.0, but reviewing a generated document meant reading Markdown in a
terminal, and the immutable versioning delivered in 1.0 had nothing that could
consume it — `v1` and `v2` sat on disk with no way to compare them.

Scope was deliberately limited to the review surface. Mission authoring,
configuration and backlog management stay on the command line.

| Feature | Status | Where it lives |
|---|---|---|
| Local web review server, no framework dependency | ✅ | `interfaces/web/server.py` |
| Engagement list with a pending-review count | ✅ | `pages.index` |
| Rendered Markdown deliverable view | ✅ | `interfaces/web/markdown.py` |
| Version selector across a deliverable's history | ✅ | `pages.deliverable_view` |
| **Version diff with added/removed line counts** | ✅ | `interfaces/web/diff.py` |
| Approve / request changes inline, with feedback | ✅ | `pages._review_form` |
| Feedback mandatory when sending work back | ✅ | It becomes the rework brief |
| Long-running execution off the request thread | ✅ | `EngagementRunner` |
| Unreadable engagements surfaced, never hidden | ✅ | `ReviewApp._index` |
| XSS-safe rendering of model-generated content | ✅ | Escape-first + CSP |

## Success criteria

| Criterion | Met |
|---|---|
| A deliverable can be read as a document, not raw Markdown | ✅ |
| A reviewer can see what a revision changed | ✅ |
| Approve and reject are possible without touching the CLI | ✅ |
| Rejection cannot happen without feedback for the model | ✅ |
| No new runtime dependency | ✅ |

## Explicitly not in 1.5

Mission authoring in the browser, configuration UI, dashboards and charts.
Authentication and multi-user access are **4.0** — the server binds to
localhost and says so.

The adapter rule these interfaces follow is recorded in
[12-interfaces.md](12-interfaces.md).

---

# Hyperium 2.0 — Methodologies as first-class objects

**Status: 🟡 75% delivered — 6 ✅ · 2 ⬜ of 8 features**

## Goal

Make the *plan* deterministic, not just its ordering. A methodology, not the
model, decides what work an engagement contains. Recorded in
[ADR-005](ADR-005-methodology-driven-planning.md).

| Feature | Status | Where it lives |
|---|---|---|
| Methodology model — principles, stages, deliverables, quality gates | ✅ | `core/methodologies/methodology.py` |
| Deterministic plan generation from a methodology | ✅ | `core/planning/methodology_planner.py` |
| Methodologies authored as data, validated on load | ✅ | `methodologies/*.json`, `JsonMethodologyRepository` |
| Technique library bound to capabilities | ✅ | `methodologies/techniques/`, 14 techniques |
| Template structure driving the deliverable | ✅ | `DeliverableTemplate.sections` |
| Quality gates between stages | ✅ | `core/methodologies/quality_gate.py` |
| Document generation: Word, PowerPoint, Excel, BPMN | ⬜ | Markdown only. Needs new dependencies |
| Second LLM provider (Claude, OpenAI) | ⬜ | Ollama only; the abstraction is unexercised |

Shipped methodologies: **business-analysis** (3 stages, 16 activities),
**solution-delivery** (4 stages, 15 activities), **process-improvement**
(4 stages, 15 activities).

## Success criteria

| Criterion | Met |
|---|---|
| Multiple methodologies supported, selectable per mission | ✅ |
| A methodology, not the LLM, decides the plan | ✅ |
| The same mission and methodology produce the same work every run | ✅ |
| A stage cannot complete until its quality gate passes | ✅ |
| Reusable consulting techniques bound to capabilities | ✅ |
| Deliverables produced in the formats clients actually receive | ⬜ |

## What changed in the model's role

The analysis step no longer decomposes a mission. It contributes
understanding — summary, assumptions, risks — and recommends a methodology
from the registry. It cannot invent one.

Because the plan no longer depends on it, **a failed analysis no longer costs
the engagement**: it proceeds on the mission's methodology or the default.

## What is left for 2.0

1. **Document generation.** Markdown is not what a client receives. Word,
   PowerPoint and BPMN each need a dependency, which is the first real
   argument for adding one since the project began.
2. **A second LLM provider.** The `LLMProvider` abstraction has never been run
   against anything but Ollama, so it is unproven.

## Known fragility

`required_sections` on a quality gate is a case-insensitive substring match.
A live run blocked a stage because a business case was headed
"Recommendation" rather than "Recommendations" — the gate was correct and the
document was arguably fine. Keep gate checks few and forgiving until something
structural replaces substring matching.

---

# Hyperium 3.0 — Organizational memory

**Status: ⬜ Not started. No `core/knowledge/` exists.**

| Feature | Status | Note |
|---|---|---|
| Knowledge base | ⬜ | |
| Lessons learned captured from completed projects | ⬜ | |
| Best practices and pattern library | ⬜ | |
| Semantic search over prior work | ⬜ | |
| Retrieval-augmented generation | ⬜ | |
| Knowledge injected into activity execution | ⬜ | Within-project context exists; nothing survives the project |

## Success criteria

- Hyperium improves after every completed project.
- Projects reuse historical knowledge.
- An executing Resource receives relevant prior knowledge as context.

Principle 4 of the vision — *knowledge compounds* — is currently unmet.
`ActivityPromptBuilder` passes upstream activity output as context, which is
within-project memory only.

---

# Hyperium 4.0 — Enterprise-scale delivery

**Status: ⬜ Not started**

| Feature | Status | Note |
|---|---|---|
| Parallel execution across independent graph branches | ⬜ | The dependency graph already expresses it |
| Multi-project execution | ⬜ | |
| Governance points beyond the 1.0 approval gate | ⬜ | |
| Audit trail — who approved what, when | ⬜ | Review summaries are stored; there is no audit log |
| Log correlation by mission and activity id | ⬜ | Logging exists but is not correlated |
| Resource capacity and booking | ⬜ | The allocator has no capacity model; one resource takes every activity |
| Distributed and resumable execution | 🟡 | Resumable ✅ (1.0); distributed ⬜ |
| Security and access control | ⬜ | |
| External integration: Git, Jira, UiPath | ⬜ | |

---

# Hyperium 5.0 — Digital Consulting Organization

**Status: ⬜ Not started**

| Feature | Status |
|---|---|
| Capability-matched teams collaborating autonomously | ⬜ |
| Portfolio management across missions | ⬜ |
| Executive reporting | ⬜ |
| Strategic planning | ⬜ |
| Continuous optimisation | ⬜ |

The mission backlog delivered in 1.0 is the first step toward portfolio
management.

---

# Delivery summary

| Version | Theme | Delivered |
|---|---|---|
| **1.0** | Execute one mission end to end | ✅ **28 / 28** |
| **1.5** | A usable human loop | ✅ **10 / 10** |
| **2.0** | Methodologies as first-class objects | 🟡 **6 / 8 (75%)** |
| **3.0** | Organizational memory | 0 / 6 |
| **4.0** | Enterprise-scale delivery | 0 / 9 |
| **5.0** | Digital Consulting Organization | 0 / 5 |

Progress against the five guiding principles of
[01-vision.md](01-vision.md):

| Principle | State |
|---|---|
| 1. Methodology First | ✅ A methodology authors every plan |
| 2. Deliverables Create Value | ✅ Versioned deliverables are produced and stored |
| 3. AI Generates Content | ✅ Content is generated; ⬜ but AI still invents the methodology |
| 4. Knowledge Compounds | ⬜ 3.0 — nothing survives a project |
| 5. Human Oversight | ✅ A blocking gate with approve, reject and rework |

---

# Phase Mapping

The former `docs/roadmap.md` used a Phase 1–6 numbering and has been retired.

| Former phase | Content | Now tracked in |
|---|---|---|
| Phase 1 | Single agent, Workspace, Project | **1.0 ✅** — reframed as a single Resource executing an Activity |
| Phase 2 | Multi-agent, Reviewer, Scheduler | **1.0 ✅** — Resources matched by Capability, dependency-ordered scheduling. The AI Reviewer became a **human** gate |
| Phase 3 | Memory, Knowledge base, RAG | **3.0 ⬜** |
| Phase 4 | LangGraph, Parallel execution, Human approval | Human approval → **1.0 ✅**; parallel execution → **4.0 ⬜**; LangGraph is an implementation choice, not a roadmap item |
| Phase 5 | Word, PowerPoint, BPMN, Excel | **2.0 ⬜** |
| Phase 6 | UiPath, Git, Jira | **4.0 ⬜** |

"Single agent" and "multi-agent" are no longer meaningful milestones under
[ADR-003](ADR-003-capability-based-execution.md). The equivalent question is how
many Capabilities can be matched and allocated within a plan.

---

# Guiding Principle

Every new feature should move Hyperium closer to its long-term vision.
Features that do not contribute to the roadmap should be reconsidered.

Status in this document is verified, not asserted. A feature that exists as a
class but does not run is ⬜, not ✅ — reading status from the existence of
filenames is how the first gap analysis concluded the runtime was nearly
complete when nothing executed at all.
