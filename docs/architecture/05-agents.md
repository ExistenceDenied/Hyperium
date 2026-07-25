# Hyperium Agents

> Version: 1.0

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