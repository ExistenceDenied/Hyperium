# ADR-004: Execution Model

> Version: 1.0
> Status: **Accepted**
> Supersedes the agent-binding parts of `02-domain-model.md`, `05-agents.md` and `06-runtime.md`.

---

# Context

Two incompatible execution models coexisted in the codebase, each with its own
entry point, its own `Project` class and its own `Deliverable` class. They
shared no types.

- **Stack A** implemented `02-domain-model.md`, `05-agents.md` and
  `06-runtime.md`: a `Runtime` loop, an `AgentRegistry`, and `WorkItem`s bound
  to exactly one agent class.
- **Stack B** implemented `ADR-001`, `ADR-002` and `ADR-003`: `Mission`,
  `Activity`, `Capability`, `Resource`.

Neither ran end to end. Stack A crashed on an argument mismatch before any
agent executed. Stack B ran to completion but discarded the model's output at
the analysis boundary, producing an empty plan and reporting success.

Three capabilities the vision depends on were absent from both, and absent
from the architecture documents except as "Future Capabilities":

1. **Dependency sequencing.** `Activity` had no dependency field.
   `WorkItem.dependencies` existed and was read by nothing. Execution order
   was whatever the model happened to emit — meaning the AI, not Hyperium,
   determined the execution structure. `03-methodologies.md` forbids exactly
   this.
2. **Deliverable content.** Stack B's `Deliverable` had no content field, so
   the target model had nowhere to put the artifact clients pay for. Stack A
   stored a filename and wrote revisions to the same path, destroying the
   version that had just been reviewed.
3. **Persistence.** No repository, no serialisation, no resume. A human
   approval gate requires a run to pause, the process to exit, and the
   engagement to continue later. Without durable state, principle 5 of the
   vision was not merely unimplemented — it was unreachable.

---

# Decision

## 1. Capability-based execution wins

Work is assigned to capabilities, not to agents, as stated in `ADR-003`.
`AgentRegistry` and the `WorkItem -> Agent` binding are retired.

**Agents are reframed, not deleted.** The consulting expertise that lived in
agent system prompts now lives in a capability prompt library. Expertise is
bound to a capability rather than to a class, so the same activity can be
satisfied by an AI, a human or an external service without the domain
changing.

```
Activity ──requires──> Capability <──provides── Resource
                            │
                            └──> CapabilityPrompt (persona + guidance)
```

## 2. Activities form a directed acyclic graph

`Activity` gains `key` and `depends_on`. Dependencies are expressed between
keys rather than UUIDs so a plan stays readable, survives serialisation, and
can be authored by a methodology as easily as by an analysis step.

`PlanningService` resolves the graph into a deterministic execution order and
**rejects** any graph containing a cycle, a self-reference, a duplicate key or
an unknown reference. An unsatisfiable graph is a planning failure, not
something to execute in arbitrary order.

The analysis step supplies the edges; Hyperium decides the order. This is the
concrete form of "Hyperium determines the execution structure."

## 3. A deliverable is both work breakdown and artifact

`Deliverable` gains `versions` and `status`. Every revision creates a new
`DeliverableVersion` with its own filename, so the version that was reviewed
is never overwritten by the one that replaces it.

Content is written through an `ArtifactStore` interface. Where artifacts live
stays an infrastructure decision; the execution layer never touches the
filesystem.

## 4. The approval gate blocks, and the engagement persists

A deliverable moves to `AWAITING_APPROVAL` when every activity producing it
has completed. An activity is ready only when its dependencies have completed
**and** the deliverable each dependency belongs to has been approved.

`ExecutionEngine.execute` is re-entrant. It runs everything it is permitted to
run, then returns `AWAITING_APPROVAL` — a success state, not a failure.
`ProjectRepository` serialises the whole object graph to JSON, so the process
may exit while a human decides and resume exactly where it paused.

`AWAITING_APPROVAL` is therefore a first-class outcome of a run, not an error
condition.

## 5. Only AI resources execute autonomously

Human and tool resources are modelled and allocated, but their work happens
outside Hyperium. An activity allocated to a `HumanResource` is reported and
left pending rather than silently faked. The run reports `BLOCKED`, which is
honest, rather than `COMPLETED`, which would not be.

---

# Consequences

**Positive**

- One execution model, one entry point, one `Project`, one `Deliverable`.
- The deterministic-methodology thesis now has a data structure behind it.
- Human oversight is mechanically possible rather than aspirational.
- A transient provider failure no longer discards completed work.
- Humans and tools remain first-class resources in the model.

**Negative**

- Every deliverable requires an explicit approval, so a fully autonomous run
  is no longer possible without an auto-approving reviewer. This is
  deliberate; it may need an opt-out for low-stakes engagements.
- Serialisation must track the domain model. `SCHEMA_VERSION` guards this and
  a mismatch fails loudly rather than restoring a corrupt graph.
- Activities still execute sequentially. The dependency graph makes safe
  parallelism expressible, but it is not yet implemented.

**Retired**

`core/entities/`, `core/workflow/`, `core/parsers/`, `core/review/`,
`core/value_objects/`, `application/runtime/`, `application/registry/`,
`services/`, `engine/`, and `core/resources/agents/`.

---

# Alternatives considered

**Keep the agent model (`02`/`05`/`06`).** Simpler, and Stack A's working code
would have ported directly. Rejected because it makes humans and tools
second-class: an activity bound to `BusinessAnalystAgent` cannot be handed to
a person without changing the domain. That contradicts `ADR-003` and the
positioning of Hyperium as a professional-services platform rather than an
AI-agent framework.

**Hybrid — allocate by capability, execute via an agent registry.** Preserves
both models. Rejected as two indirection layers doing one job; the registry
adds no behaviour once a capability already selects the prompt strategy.

**Defer persistence.** Would have shipped visible progress sooner. Rejected
because the approval gate is not a feature that can be added on top of an
in-memory runtime — the gate *is* the pause, and a pause without durable state
is just a process that dies.

**Store deliverable content in the activity rather than the deliverable.**
Rejected because a deliverable is what the client buys and what a human
reviews; versioning and approval belong at that level, not per activity.
Activities contribute sections, which the deliverable assembles.

---

# Open questions

- Methodologies remain unimplemented. Until they exist, the analysis step
  generates the work breakdown, which `03-methodologies.md` warns against.
  ADR-005 should cover authored, deterministic methodologies.
- The Knowledge bounded context from `ADR-002` has no implementation.
- Parallel execution of independent activities is expressible but not built.
- Timeouts are still absent; only retries exist.
