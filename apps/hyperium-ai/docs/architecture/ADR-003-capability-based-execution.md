# ADR-003 – Capability Based Execution

## Status

Accepted

## Context

Traditional AI frameworks assign work directly to agents.

Examples include:

- BusinessAnalystAgent
- ResearchAgent
- CodingAgent

This tightly couples work to a specific implementation.

Hyperium models professional services rather than AI agents.

Professional work requires capabilities.

Capabilities can be provided by humans, AI systems, software tools or external services.

## Decision

Work is assigned to capabilities, not to agents.

Resources provide one or more capabilities.

The execution process becomes:

Mission
→ Analysis
→ Planning
→ Activities
→ Required Capabilities
→ Resource Allocation
→ Execution
→ Knowledge

## Resource Types

Resources may include:

- Human Resources
- AI Resources
- Software Tools
- External Services

All resources expose capabilities.

## Capability Examples

Examples of capabilities include:

- Business Analysis
- Research
- Requirements Engineering
- Architecture
- BPMN Modelling
- Data Analysis
- Technical Writing
- Presentation Design
- Software Development
- Testing
- Review
- Facilitation

Capabilities are independent of the resource providing them.

## Consequences

Activities become reusable.

Resource allocation becomes dynamic.

Multiple resources may provide the same capability.

New AI models can be introduced without changing the business model.

Human consultants remain first-class resources.

## Principles

Activities require capabilities.

Resources provide capabilities.

Execution allocates resources to activities.

Capabilities belong to the business domain.

Resources belong to the execution domain.

AI is an implementation detail.