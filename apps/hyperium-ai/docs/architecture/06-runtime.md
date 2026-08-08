# Hyperium Runtime

> Version: 1.0
> Status: **PARTIALLY SUPERSEDED**

---

> ## ⚠ SUPERSEDED NOTICE
>
> The agent-resolution mechanics described here are superseded by
> [ADR-003 – Capability Based Execution](ADR-003-capability-based-execution.md).
> The Runtime no longer resolves a Work Item to an Agent; it allocates a
> **Resource** to an **Activity** by matching **Capabilities**.
>
> **Superseded sections — do not build against these:**
>
> | Section | Superseded by |
> |---|---|
> | *Responsibilities* — "executing Work Items", "selecting the appropriate Agent" | Executing **Activities**; allocating a **Resource** whose Capabilities satisfy the Activity's `required_capabilities`. |
> | *Runtime Components* diagram (`Scheduler → Agent Registry → Agent`) | `Execution Plan → Capability Matcher → Resource Allocator → Resource` (`application/execution/`). |
> | *Agent Registry* (the whole section) | **Capability Catalogue** + **Capability Matcher** + **Resource Allocator**. `AgentRegistry` is retired. |
> | *Execution Cycle* — "Select Work Item → Resolve Agent → Execute Agent" | "Select Activity (topological order) → Match Capabilities → Allocate Resource → Execute → Store Deliverable Version → Review". |
> | *Workflow Instance* — "active work items / completed work items" | Read **Activities**. |
> | *Scheduler* — "selecting executable Work Items" | Read **Activities**; ordering is produced by the Activity dependency graph (`core/planning/dependency_graph.py`). |
>
> **Still valid — this document remains the reference for:**
>
> - the separation of orchestration from execution (the guiding principle)
> - the Review Loop and the rule that a rejected Deliverable generates follow-up work
> - State Tracking: the Runtime owns execution state, executing Resources do not
> - Failure Handling responsibilities: retry policies, timeouts, dependency failures, invalid results, logging — **none of which are implemented yet** (see [11-gap-analysis.md](11-gap-analysis.md))
> - Future Capabilities, of which human approval tasks and persistent execution are now in progress
>
> Where the valid sections say "Agent", read **Resource**. Where they say
> "Work Item", read **Activity**.

---

# Purpose

The Runtime is responsible for executing Projects.

It orchestrates the execution of Work Items while enforcing the Workflow defined by the selected Methodology.

The Runtime is the operating system of Hyperium.

---

# Responsibilities

The Runtime is responsible for:

- executing Work Items
- selecting the appropriate Agent
- respecting Workflow dependencies
- scheduling work
- managing review cycles
- tracking Project progress
- detecting Project completion

The Runtime does **not** perform consultancy work itself.

---

# Runtime Components

The Runtime consists of several logical components.

```
Project
    │
    ▼
Workflow Instance
    │
    ▼
Scheduler
    │
    ▼
Agent Registry
    │
    ▼
Agent
    │
    ▼
Deliverables
    │
    ▼
Review
    │
    ▼
Scheduler
```

---

# Workflow Instance

Every Project owns a Workflow Instance.

The Workflow Instance contains:

- active stage
- completed stages
- active work items
- completed work items
- pending reviews

The Methodology remains immutable.

The Workflow Instance represents project execution.

---

# Scheduler

The Scheduler decides which Work Item should execute next.

Responsibilities include:

- checking dependencies
- selecting executable Work Items
- enabling parallel execution
- detecting deadlocks
- monitoring completion

The Scheduler never performs consultancy work.

---

# Agent Registry

The Agent Registry resolves Work Items to Agent implementations.

Example:

```
Business Analyst

↓

BusinessAnalystAgent
```

The Runtime never instantiates Agents directly.

---

# Execution Cycle

The Runtime repeatedly performs the following cycle.

```
Select Work Item

↓

Resolve Agent

↓

Execute Agent

↓

Store Deliverables

↓

Request Review

↓

Process Review

↓

Create Follow-up Work

↓

Repeat
```

Execution ends when no executable Work Items remain.

---

# Review Loop

Every Deliverable may enter a review cycle.

```
Deliverable

↓

Review

↓

Approved?
      │
 ┌────┴────┐
 │         │
Yes       No
 │         │
 ▼         ▼

Continue  Improvement Work Item
```

Improvement Work Items become part of the Project.

---

# State Tracking

The Runtime maintains Project state.

Examples:

- Not Started
- Running
- Waiting
- Reviewing
- Completed
- Failed

The Runtime owns execution state.

Agents do not.

---

# Failure Handling

The Runtime is responsible for:

- retry policies
- timeout handling
- dependency failures
- invalid agent results
- logging

Agents should only report failures.

---

# Future Capabilities

Future Runtime versions may support:

- distributed execution
- multiple LLM providers
- human approval tasks
- asynchronous execution
- event-driven execution
- persistent execution
- workflow resume

The Runtime architecture should remain stable.

---

# Guiding Principle

Agents perform work.

The Runtime orchestrates work.

The separation between orchestration and execution should always remain clear.