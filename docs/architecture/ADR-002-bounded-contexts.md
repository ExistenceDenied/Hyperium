# ADR-002 – Bounded Contexts

## Status

Accepted

## Context

Hyperium is an Operating System for Professional Services.

To keep the platform maintainable and scalable, the domain is divided into bounded contexts.

Each bounded context owns its own concepts, business rules and services.

Dependencies between contexts should be minimized.

---

# Bounded Contexts

## Missions

Responsible for defining business objectives.

Owns:

- Mission
- Objective
- Stakeholder
- Constraint
- Success Criterion

A Mission describes **what** should be achieved.

It never describes **how**.

---

## Analysis

Responsible for understanding a mission.

Owns:

- MissionAnalysisService
- AnalysisResult
- Prompt Builders
- Result Parsers

Analysis determines:

- domain
- assumptions
- risks
- disciplines
- recommended deliverables

Analysis never creates execution plans.

---

## Planning

Responsible for translating analysis into executable work.

Owns:

- Execution Strategy
- Project
- Work Items
- Dependencies
- Scheduling

Planning decides **how** the mission should be executed.

---

## Execution

Responsible for performing work.

Owns:

- Agents
- Human Resources
- AI Resources
- External Tools

Execution never determines business goals.

---

## Knowledge

Responsible for capturing reusable knowledge.

Owns:

- Lessons Learned
- Templates
- Methodologies
- Best Practices
- Knowledge Graph

Knowledge continuously improves future missions.

---

## AI Infrastructure

Responsible for interacting with AI providers.

Owns:

- LLMService
- Provider implementations
- Prompt execution
- Structured output

This context knows nothing about consulting.

It only knows how to communicate with AI models.

---

# Dependency Rules

Missions
↓

Analysis
↓

Planning
↓

Execution
↓

Knowledge

AI Infrastructure is a supporting context and may be used by Analysis, Planning and Execution.

Business contexts must never depend directly on AI providers.

---

# Guiding Principles

Business before Technology.

Understand before Planning.

Planning before Execution.

Knowledge after Execution.

AI is an implementation detail.