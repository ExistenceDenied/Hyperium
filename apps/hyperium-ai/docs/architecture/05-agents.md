# Hyperium Agents

> Version: 1.0
> Status: **PARTIALLY SUPERSEDED**

---

> ## ⚠ SUPERSEDED NOTICE
>
> The binding of work to Agents described here is superseded by
> [ADR-003 – Capability Based Execution](ADR-003-capability-based-execution.md).
>
> **Agents are not deleted — they are reframed.** A role such as "Business Analyst"
> is no longer a class that owns work. It is a **capability prompt strategy**: a
> bundle of prompt and technique bound to a **Capability**. An **AIResource**
> executes an **Activity** by selecting the prompt strategy for the capability the
> Activity requires. This is implemented in
> `core/execution/prompting/capability_prompt_library.py`; the personas below now
> live there as capability prompts rather than as agent classes.
>
> **Superseded sections — do not build against these:**
>
> | Section | Superseded by |
> |---|---|
> | *Purpose* — "Agents are autonomous specialists responsible for executing Work Items" | Activities require Capabilities. Resources provide Capabilities. A Resource is allocated to an Activity; no Agent owns a unit of work. |
> | *Responsibilities* — "understanding its assigned Work Item" | A Resource is allocated an **Activity**, not a Work Item. |
> | *Agent Inputs* — "Work Item" as an input | Read **Activity**. |
> | *Agent Outputs* — "New Work Items" in an Agent Result | Read **new Activities**, added to the plan and re-ordered by the dependency graph. |
> | *Agent Types* (Business Analyst, Enterprise Architect, Solution Architect, Developer, Tester, Reviewer) | These are **Capabilities** in the capability catalogue, each with a prompt strategy. They are no longer a class hierarchy. |
> | *Extensibility* — "implementing the Agent interface, registering the Agent, defining its supported Work Items" | Register a **Capability** in the catalogue, supply its **prompt strategy**, and declare which **Resources** provide it. `AgentRegistry` is retired. |
>
> **Still valid — this document remains the reference for:**
>
> - the execution lifecycle (Prepare → Execute → Validate → Produce → Return Result), which now describes how a Resource executes an Activity
> - the non-responsibilities: execution never does planning, scheduling, governance or quality-gate decisions
> - collaboration through Deliverables only — Resources never message each other
> - LLM independence: execution talks only to the LLM abstraction layer
>
> Where the valid sections say "Agent", read **Resource**. Where they say
> "Work Item", read **Activity**.

---

# Purpose

Agents are autonomous specialists responsible for executing Work Items.

Each Agent represents a professional consulting role with domain-specific expertise.

Agents generate, improve or review Deliverables.

Agents do not manage projects.

Agents do not define methodologies.

Agents do not control workflows.

---

# Responsibilities

Every Agent is responsible for:

- understanding its assigned Work Item
- collecting required input
- producing Deliverables
- validating its own output
- submitting the Deliverable for review

---

# Non-Responsibilities

Agents are NOT responsible for:

- project planning
- workflow management
- scheduling
- governance
- quality gate decisions
- project reporting

These responsibilities belong to Hyperium itself.

---

# Agent Lifecycle

Every Agent follows the same lifecycle.

```
Prepare

↓

Execute

↓

Validate

↓

Produce

↓

Return Result
```

Each implementation may extend these steps but should preserve the lifecycle.

---

# Agent Inputs

An Agent may receive:

- Project
- Work Item
- Existing Deliverables
- Previous Reviews
- Templates
- Methodology Context
- Workflow Context
- Knowledge Assets

Agents should receive all required context from Hyperium.

They should not retrieve information independently unless explicitly permitted.

---

# Agent Outputs

Every Agent returns an Agent Result.

An Agent Result may contain:

- Deliverables
- Observations
- New Work Items
- Review Requests

Agents never modify the Project directly.

---

# Agent Types

Current Agents include:

## Business Analyst

Produces:

- Requirements
- Process Models
- Business Rules
- Stakeholder Analysis

---

## Enterprise Architect

Produces:

- Capability Models
- Architecture Principles
- Reference Architectures

---

## Solution Architect

Produces:

- Solution Designs
- Integration Designs
- Technical Specifications

---

## Developer

Produces:

- Source Code
- Database Models
- API Specifications

---

## Tester

Produces:

- Test Plans
- Test Cases
- Validation Reports

---

## Reviewer

Evaluates Deliverables.

Produces:

- Review Results
- Improvement Requests
- Approval Decisions

The Reviewer never owns Deliverables.

---

# Agent Collaboration

Agents collaborate through Deliverables.

Example:

Business Analyst

↓

Requirements

↓

Solution Architect

↓

Architecture

↓

Developer

↓

Implementation

↓

Tester

↓

Validation

Agents never communicate directly.

Deliverables are the communication mechanism.

---

# LLM Independence

Agents should not depend on a specific AI provider.

Agents interact only with the LLM abstraction layer.

This allows Hyperium to switch providers without changing Agent implementations.

---

# Extensibility

Adding a new Agent should require:

- implementing the Agent interface
- registering the Agent
- defining its supported Work Items

No existing Agent should require modification.

---

# Guiding Principle

Agents represent professional expertise.

Hyperium represents governance.

This separation keeps the platform maintainable and predictable.