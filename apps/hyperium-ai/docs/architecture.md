# Hyperium AI Architecture

> Version: 0.1
> Status: **HISTORICAL — SUPERSEDED**

---

> ## ⚠ HISTORICAL DOCUMENT
>
> This is the original v0.1 architecture sketch. It is kept for provenance only.
> **It is not the current architecture and must not be used as a reference.**
>
> It is superseded in full by the **v1.0 series** in [`docs/architecture/`](architecture/),
> and specifically by:
>
> - [ADR-001 – Mission Driven Architecture](architecture/ADR-001-mission-driven-architecture.md) — **Mission**, not Project, is the highest-level business concept. This document's "Everything is a Project" principle is superseded.
> - [ADR-002 – Bounded Contexts](architecture/ADR-002-bounded-contexts.md) — Missions / Analysis / Planning / Execution / Knowledge / AI Infrastructure.
> - [ADR-003 – Capability Based Execution](architecture/ADR-003-capability-based-execution.md) — work is assigned to **Capabilities**, not Agents. This document's "Agents receive Tasks" and CEO → Scheduler → Tasks → Agents chain are superseded.
> - [00-core-domain.md](architecture/00-core-domain.md) — the current ubiquitous language. "Task" is retired vocabulary; the atomic unit of work is the **Activity**.
>
> Principles from this document that **did survive** into v1.0 are restated there:
> deliverables as first-class citizens, deterministic workflow with AI producing
> content only, communication through deliverables rather than messages, and a
> replaceable LLM layer.

---

# Vision

Hyperium AI is a digital consultancy organization.

The objective is not to build a chatbot.

The objective is to build autonomous consulting teams that produce professional deliverables.

---

# Core Principles

## 1. Everything is a Project

Every execution belongs to a Project.

A Project owns:

- goal
- workspace
- deliverables
- tasks
- workflow state

Nothing exists outside a project.

---

## 2. Agents never talk to each other

Agents never exchange messages.

Instead they communicate through Deliverables.

Business Analyst

↓

Requirements.md

↓

Enterprise Architect

↓

Architecture.md

↓

Developer

↓

Source Code

---

## 3. Agents receive Tasks

Agents never receive prompts.

They receive Tasks.

A Task contains:

- objective
- inputs
- expected output
- owner

---

## 4. Deliverables are first-class citizens

Deliverables are not files.

Files are only one implementation.

A Deliverable has:

- owner
- version
- quality
- approval status
- filename

---

## 5. AI creates content

AI never decides the workflow.

AI creates:

- requirements
- diagrams
- slides
- documentation
- code
- reviews

---

## 6. Scheduler controls execution

Workflow is deterministic.

The Scheduler decides:

- next task
- dependencies
- retries
- approvals

---

## 7. Workspace is the single source of truth

Every artifact exists in the Workspace.

No agent owns data.

---

## 8. LLM is replaceable

Agents never directly call Ollama.

Agents only use LLMService.

Supported providers should eventually include:

- Ollama
- OpenAI
- Claude
- Azure OpenAI
- Local inference servers

---

# Long-term Architecture

Business Owner

↓

CEO

↓

Scheduler

↓

Tasks

↓

Agents

↓

Deliverables

↓

Workspace

↓

Reviewer

↓

CEO

↓

Done