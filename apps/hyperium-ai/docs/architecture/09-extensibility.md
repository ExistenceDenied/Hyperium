# Hyperium Extensibility

> Version: 1.0

---

# Purpose

Hyperium is designed to evolve continuously.

New capabilities should be added through extension rather than modification.

The architecture should support growth without requiring changes to existing components.

---

# Open for Extension

Hyperium should be open for extension and closed for modification.

Adding new functionality should rarely require changing existing code.

Instead, new functionality should be introduced through new implementations.

---

# Extensible Components

The following concepts should be extensible.

## Methodologies

New methodologies should be added without changing the Runtime.

Examples:

- Business Analysis
- Enterprise Architecture
- Compliance
- AI Strategy

---

## Workflows

New workflows should be introduced independently.

Existing workflows should remain unchanged.

---

## Techniques

New consulting techniques should be added independently.

Examples:

- BPMN
- Fishbone
- Event Storming
- Domain Storytelling
- Wardley Mapping

---

## Agents

Adding a new Agent should require:

- implementing the Agent interface
- registering the Agent

No existing Agent should require modification.

---

## Reviews

Different review strategies should coexist.

Examples:

- Quality Review
- Architecture Review
- Security Review
- Compliance Review

---

## Knowledge Assets

New knowledge categories should be supported.

Examples:

- Templates
- Patterns
- Playbooks
- Examples
- Lessons Learned

---

## LLM Providers

New AI providers should be introduced through Provider implementations.

Examples:

- Ollama
- OpenAI
- Anthropic
- Azure OpenAI

Agents should remain unchanged.

---

# Dependency Direction

Dependencies should always point inward.

```
Infrastructure

↓

AI Layer

↓

Execution Layer

↓

Business Layer
```

Business concepts should never depend on infrastructure.

---

# Plugin Architecture

Future versions may support plugins.

Examples:

- Methodology plugins
- Agent plugins
- Technique plugins
- Review plugins
- Knowledge plugins

Plugins should integrate through well-defined interfaces.

---

# Configuration over Code

Whenever possible, behaviour should be configured rather than hardcoded.

Examples include:

- model selection
- review thresholds
- workflow parameters
- retry policies

---

# Backward Compatibility

Existing Projects should continue to run after platform upgrades whenever reasonably possible.

Breaking changes should be minimized.

---

# Guiding Principle

Hyperium should grow by adding new capabilities.

Existing components should remain stable.