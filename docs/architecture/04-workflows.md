# Hyperium Workflows

> Version: 1.0
> Status: **SUPERSEDED**

---

> ## ⚠ SUPERSEDED NOTICE
>
> **There is no `Workflow` type in Hyperium, and there is no `Work Item`.**
> This document describes a layer between Methodology and Stage that was never
> built and is not planned. Do not design against it.
>
> Superseded by [ADR-005](ADR-005-methodology-driven-planning.md): a
> `Methodology` contains `Stage`s directly, a Stage contains
> `DeliverableTemplate`s, and those contain `ActivityTemplate`s. Stage
> ordering is expanded into ordinary activity dependencies so that one
> topological sort enforces it — there is no separate workflow engine.
>
> **The ideas in this document survive; the entity does not.** Dependency
> ordering, parallelism, entry/exit conditions and review loops are all real,
> and are implemented as described in
> [ADR-005](ADR-005-methodology-driven-planning.md) and
> [ADR-006](ADR-006-plan-owns-its-governance.md). Read it for the reasoning,
> not for the model.


---

# Purpose

A Workflow defines the execution path of a project.

It translates a Methodology into an ordered sequence of executable activities.

A Workflow describes **when** work happens.

It does not describe **how** work is performed.

---

# Relationship with the Domain

```
Methodology
        │
        ▼
Workflow
        │
        ▼
Stages
        │
        ▼
Work Items
```

A Methodology defines one or more Workflows.

A Workflow is instantiated for every Project.

---

# Definition

A Workflow is a directed sequence of stages connected by execution rules.

Its responsibilities are:

- ordering work
- defining dependencies
- enabling parallel execution
- defining completion criteria

A Workflow never generates deliverable content.

---

# Workflow Structure

A Workflow consists of:

- Metadata
- Stages
- Dependencies
- Entry Conditions
- Exit Conditions

---

# Workflow Metadata

Every Workflow contains:

- Name
- Description
- Version
- Methodology
- Author

---

# Stages

A Stage groups related work.

Example:

```
Discovery

↓

Analysis

↓

Design

↓

Implementation

↓

Validation
```

Stages improve:

- reporting
- monitoring
- project governance

---

# Work Items

Stages contain Work Items.

Examples:

Discovery

- Interview Stakeholders
- Collect Existing Documentation
- Understand Current Process

Analysis

- Model BPMN Process
- Identify Pain Points
- Define Requirements

---

# Dependencies

Work Items may depend on previous work.

Example:

```
Requirements
        │
        ▼
Architecture
        │
        ▼
Development
```

A Work Item cannot start until its dependencies are satisfied.

---

# Parallel Execution

Independent Work Items may execute simultaneously.

Example:

```
Requirements
       │
       ├──────────────┐
       ▼              ▼

Security Review    UX Design

       └──────────────┘
              ▼

Architecture Review
```

Parallel execution improves throughput.

---

# Quality Gates

A Workflow defines quality checkpoints.

Examples:

- Discovery Approved
- Requirements Approved
- Design Approved
- Testing Complete

A Stage cannot complete until its quality gate succeeds.

---

# Review Loops

Hyperium supports iterative improvement.

Example:

```
Create Deliverable

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

Next     Improve
Stage        │
             ▼
          Review
```

Review loops are part of the Workflow.

They are not runtime exceptions.

---

# Workflow Independence

A Workflow should not depend on:

- AI models
- Agent implementations
- Prompt engineering
- File storage

It only defines execution logic.

---

# Future Extensions

Future versions may support:

- conditional branches
- event-driven workflows
- approval workflows
- client interaction stages
- external system integration

The core Workflow model should remain stable.

---

# Guiding Principle

A Workflow represents consulting governance.

Artificial Intelligence executes Work Items.

Hyperium controls the Workflow.