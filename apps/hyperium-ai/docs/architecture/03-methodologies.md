# Hyperium Methodologies

> Version: 1.0

---

# Purpose

A Methodology defines **how a specific type of consultancy engagement is executed**.

It captures proven consulting practices and transforms them into repeatable workflows that can be executed autonomously by Hyperium.

Methodologies are one of Hyperium's primary competitive advantages.

---

# Definition

A Methodology is a reusable blueprint for solving a category of business problems.

It defines:

- the objective
- the phases
- the recommended techniques
- the expected deliverables
- the quality gates

A Methodology does **not** contain project-specific information.

---

# Relationship with Projects

```
Project
    │
    ▼
Methodology
    │
    ▼
Workflow
```

Each Project selects exactly one Methodology.

A Methodology may be reused by thousands of Projects.

---

# Methodology Structure

Every Methodology contains:

## Metadata

Examples:

- Name
- Description
- Version
- Author
- Applicable industries
- Applicable project types

---

## Stages

A Methodology consists of multiple stages.

Example:

Business Analysis

```
Discovery

↓

Current State

↓

Analysis

↓

Future State

↓

Business Case

↓

Roadmap
```

---

## Techniques

Each stage recommends one or more consulting techniques.

Examples:

- Stakeholder Interviews
- BPMN
- Event Storming
- Fishbone Analysis
- SWOT
- Five Whys
- Capability Mapping

Techniques describe **how** work is performed.

---

## Deliverables

Every Methodology defines expected deliverables.

Example:

Business Analysis

- Stakeholder Map
- Process Model
- Requirements Specification
- Business Case
- Roadmap

---

## Quality Gates

Each Methodology defines checkpoints.

Examples:

- Discovery approved
- Requirements reviewed
- Architecture validated
- Business case accepted

Quality gates prevent poor deliverables from propagating.

---

# Methodology Independence

Methodologies should not depend on:

- LLM providers
- specific Agents
- implementation details
- runtime configuration

They represent consulting knowledge.

---

# Examples

Possible Methodologies include:

- Business Analysis
- Enterprise Architecture
- Software Delivery
- Compliance Assessment
- Data Migration
- AI Strategy
- Operating Model Design
- Target Operating Model
- Process Optimization
- AML Transformation

New methodologies should be addable without changing the Runtime.

---

# Workflow Generation

A Methodology generates a Workflow.

```
Methodology

↓

Workflow

↓

Stages

↓

Work Items
```

The Workflow is deterministic.

Artificial Intelligence generates the content of the deliverables.

Hyperium determines the execution structure.

---

# Guiding Principle

Consultants should be able to recognise their own methodology inside Hyperium.

Hyperium should automate methodologies.

It should not invent them.