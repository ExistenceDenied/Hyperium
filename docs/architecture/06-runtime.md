# Hyperium Runtime

> Version: 1.0

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