# Gap Analysis

> Version: 3.0
> Method: read against the repository, not against memory. Every claim below was
> verified by inspecting the source tree and running the code. Counts are stated
> as measured.

---

# Purpose

This document compares the current implementation with the target architecture
defined by [ADR-001](ADR-001-mission-driven-architecture.md),
[ADR-002](ADR-002-bounded-contexts.md),
[ADR-003](ADR-003-capability-based-execution.md),
[ADR-004](ADR-004-execution-model.md) and
[ADR-005](ADR-005-methodology-driven-planning.md).

It is deliberately unflattering. A gap analysis that reports comfort is useless.

---

# Headline

**One stack, and the plan is no longer written by the model.**

A methodology authors the work breakdown; capability-matched resources execute
it; deliverables are versioned to disk; stages are held by checkable quality
gates that survive process exit.

Verified by live run of the shipped `business-analysis` methodology: 3 stages,
6 deliverables, 16 activities. Discovery produced two deliverables totalling
~3,100 words, the stage gate refused to open on partial approval, and the
analysis stage ran only once both were signed off.

The same run also proved the gates are not decorative: the stage stayed closed
because a generated business case was missing a section the methodology
requires.

**Methodology — the pillar this document has called the largest gap since its
first edition — is delivered.** What remains is **Knowledge**: nothing survives
a project.

---

# Status Summary

| Area | Status | One-line reality |
|---|---|---|
| Mission & Mission Analysis | 🟢 Working | Mission, Objective, Constraint, Stakeholder, SuccessCriterion, validator, analysis service, strict result parser. |
| Capabilities & Resources | 🟢 Working | Capability, CapabilityRequirement, ProficiencyLevel, catalogue; Human / AI / Tool / ExternalService; matcher and two allocators. |
| Capability prompt strategies | 🟢 Working | `capability_prompt_library.py` binds persona + guidance to a capability, replacing per-agent system prompts. |
| Activity dependency graph | 🟢 Working | `topological_order()` with cycle / unknown / self / duplicate rejection; `PlanningService` orders through it; `ready_activities()` gates execution. |
| Deliverable content & versioning | 🟢 Working | Engine assembles activity output into a document; `add_version()` creates a numbered immutable version with its own filename. |
| Human approval gate | 🟢 Working | Blocks cross-deliverable work until approved; `execute()` re-entrant; `AWAITING_APPROVAL` is a success state. |
| Project & plan persistence | 🟢 Working | `ProjectRepository` + `ProjectSerializer` round-trip the whole graph to JSON, including activity status and versions. Schema-versioned. |
| Artifact persistence | 🟢 Working | `ArtifactStore` abstraction; `FileArtifactStore` for runs, `InMemoryArtifactStore` for tests. |
| Human-in-the-loop interface | 🟢 Working | `interfaces/cli.py` for the full lifecycle; `interfaces/web/` for review with rendered documents and version diffs. |
| Humans executing allocated work | 🟢 Working | `ProjectService.submit_work` / `hyperium submit`. A mixed human-AI plan now completes. |
| Configuration | 🟢 Working | `config/settings.py` with `HYPERIUM_*` environment overrides for model, temperature, workspace, state dir, retries, logging. |
| Retry | 🟢 Working | `ResilientProvider` — bounded retries, exponential backoff, empty-response detection. **Now wired** in the CLI composition root. |
| Observability | 🟡 Partial | Module loggers throughout; file + stream handlers. No correlation of events to mission/activity id, no approval audit trail. |
| Execution | 🟡 Partial | Sequential only — the graph expresses safe parallelism, the engine does not use it. |
| Timeouts | 🟢 Working | `OllamaProvider(timeout_seconds=…)`, configurable via `HYPERIUM_LLM_TIMEOUT`. |
| LLM providers | 🟡 Partial | Ollama only. The abstraction has never been exercised against a second provider. |
| Methodology | 🟢 Working | `core/methodologies/`; 3 methodologies + 14 techniques authored as JSON, validated on load. |
| Deterministic plan generation | 🟢 Working | `MethodologyPlanner`. The same mission and methodology always produce the same work. |
| Stages and quality gates | 🟢 Working | Declarative, checkable gates; a stage cannot open until the previous one passes. |
| Document formats | 🔴 Missing | Markdown only. Word / PowerPoint / BPMN each need a dependency. |
| Knowledge context | 🔴 Missing | No `core/knowledge/`. Nothing survives a project. The largest unstarted area. |
| Extensibility | 🔴 Missing | No plugin, methodology or technique registry. The seams named in [09-extensibility.md](09-extensibility.md) are not implemented. |

Legend: 🟢 Working · 🟡 Partial · 🔴 Missing

---

# Empty Files

**Zero.** The previous edition recorded 26 non-`__init__` Python files at 0
bytes — filenames announcing features that did not exist. All have been deleted
or implemented.

This matters beyond tidiness: any status read from the directory tree rather
than from file contents was wrong, and that is precisely how the first edition
of this document scored Runtime as "Mostly Complete".

---

# The Three Gaps — all now closed

Recorded with their before-state, because the delta is the useful part.

## (a) Activity dependency graph — closed

**Before:** `Activity` had no dependency field. `WorkItem.dependencies` existed
and was **read by nothing**. Plans executed in whatever order the model emitted,
which meant the AI determined the execution structure —
[03-methodologies.md](03-methodologies.md) forbids exactly this.

**Now:** `Activity.depends_on: set[str]` keyed by stable business keys.
`core/planning/dependency_graph.py` provides `topological_order()` with cycle,
unknown-dependency, self-dependency and duplicate-key rejection, and stable
tie-breaking. `PlanningService` raises rather than guessing on an unsatisfiable
graph. Upstream output is fed into downstream prompts, so work compounds.

**Residual:** execution is sequential. `ready_activities()` returns everything
runnable, but the engine iterates serially. Parallelism is expressible and not
yet built.

## (b) Deliverable content and versioning — closed

**Before:** the target `Deliverable` had **no content field** — a name with no
artifact behind it. The retired stack stored a filename and wrote revisions to
the same path, destroying the version that had just been reviewed.

**Now:** `add_version(content, created_by)` creates a numbered, content-bearing
version with its own filename. `v1` survives `v2`. Content is written through
the `ArtifactStore` abstraction, so the execution layer never touches the
filesystem.

## (c) Persistence and the approval gate — closed

**Before:** zero persistence. No repository, no serialisation of any domain
object. Every run started from nothing and lost everything. No approval concept
existed, which made principle 5 of the vision unreachable rather than merely
unimplemented.

**Now:** `ProjectRepository` serialises the whole graph — mission, analysis,
plan, allocations, activity status and output, deliverable versions and review
summaries — to schema-versioned JSON. A deliverable moves to
`AWAITING_APPROVAL` when its activities finish; cross-deliverable work refuses
to start until a human approves. Verified across separate processes.

**Two subtleties, both found by live runs rather than by the test suite, both
now covered by regression tests.**

First, the gate stops at the deliverable boundary: activities within one
deliverable build the same document, and gating them on their own deliverable's
approval deadlocks the run.

Second, once methodologies arrived the boundary had to move again — to the
**stage**. Two deliverables in the same stage that depend on each other cannot
gate each other, because the stage gate needs every deliverable complete before
it can pass. See [ADR-005](ADR-005-methodology-driven-planning.md) decision 6.

---

# Detail on Remaining Gaps

## Methodology — closed

Recorded in [ADR-005](ADR-005-methodology-driven-planning.md). Both guarantees
now hold: ordering *and* plan content are deterministic. A methodology decides
what work an engagement contains; the model writes the content and nothing
else.

**Residual fragility.** `required_sections` on a quality gate is a
case-insensitive substring match. A live run blocked a stage because a business
case was headed "Recommendation" rather than "Recommendations" — the gate was
correct and the document was arguably fine. Gate checks should stay few and
forgiving until something structural replaces substring matching.

**Not yet possible.** A methodology cannot mark a stage or deliverable as
optional, so a smaller engagement needs a separate methodology rather than a
tailored one.

## Knowledge is entirely absent

[07-knowledge.md](07-knowledge.md) describes templates, patterns, lessons
learned and retrieval. There is no `core/knowledge/`, no knowledge entity, no
store, and no injection of prior knowledge into execution.

`ActivityPromptBuilder` passes upstream activity output as context, which is
within-project memory only. Nothing survives the project, so principle 4 —
"knowledge compounds" — is unmet. Hyperium is not yet more capable after an
engagement than before it.

## Execution is sequential

`ExecutionEngine` runs an activity only when its resource is an `AIResource`;
everything else waits for a human to submit work. That part is now complete.

What remains is concurrency: `ready_activities()` returns every runnable
activity, and the engine iterates them serially. Independent branches of the
dependency graph could run at once. Two things must land first — a capacity
model on the allocator, so one resource is not assigned every parallel branch,
and deterministic message ordering in `ExecutionResult`.

## Every deliverable requires approval

A consequence of ADR-004, and deliberate. It also means a fully autonomous run
is impossible without an auto-approving reviewer. Low-stakes engagements may
need an opt-out.

## Persistence has no migration path

`SCHEMA_VERSION` is enforced strictly: a project saved under an older schema
fails to load rather than being silently misread. This is the correct default,
and it has already bitten once — engagements written before the mission backlog
landed cannot be opened.

There is no upgrade step. While the schema is still moving this is acceptable;
before anyone stores work they care about, it is not.

---

# Prioritised Recommendations

1. **Add a second LLM provider** to prove the abstraction holds. Nothing has
   ever exercised it against a provider other than Ollama — this is now the
   least-tested assumption in the platform.
2. **Generate the formats clients actually receive.** Markdown is not a
   deliverable a consultancy hands over. This is the first change that
   genuinely justifies a new dependency.
3. **Correlate logs** to mission and activity id, and record an audit trail of
   who approved what — a professional-services platform needs this.
4. **Add a capacity model to the allocator**, which is the precondition for
   parallel execution rather than a separate feature.
5. **Add a schema migration step** before anyone stores work they care about.
6. **Start `core/knowledge/`** only after the above. It is 3.0 work, and
   pretending otherwise is how the first edition of this document scored
   Runtime as "Mostly Complete".

---

# Note on Previous Versions

The first edition scored **Runtime as 🟢 Mostly Complete** on the strength of
`AgentRegistry`, `Runtime`, `Queue` and `Review Loop` existing. That was wrong
twice over: it graded the stack that has since been deleted, and it predated the
Mission / Capability / Resource layer entirely. Status was read from the
existence of filenames rather than their contents — which, in a repository with
26 empty files, is not a measurement.

The v1.0 edition of this file was written while ADR-004 was being implemented
and described a transitional state that no longer exists.

This edition grades against ADR-001 through ADR-004 and reflects a verified
end-to-end run.
