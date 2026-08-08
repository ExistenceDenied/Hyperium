# Hyperium LLM Layer

> Version: 1.0

---

> ## ⚠ PARTIALLY SUPERSEDED
>
> **`LLMService` does not exist.** It was deleted with `services/` under
> [ADR-004](ADR-004-execution-model.md). The port is
> `core/interfaces/llm_provider.LLMProvider`, with a single `generate` method,
> and `ResilientProvider` wraps it with retries and a timeout.
>
> **Still valid:** the isolation goal, provider abstraction, and the rule that
> nothing in the domain may import a provider — now enforced by
> `tests/test_architecture.py::test_the_domain_never_depends_on_an_ai_provider`.
>
> **Not built:** streaming, tool calling, model selection, and structured
> output at the provider level. Response validation happens in the domain
> (`AnalysisResultParser`), not in this layer as described below.
>
> **Superseded vocabulary:** "Agents" — prompts live in
> `core/execution/prompting/`, bound to capabilities rather than agent classes
> ([ADR-003](ADR-003-capability-based-execution.md)).


# Purpose

The LLM Layer abstracts all interaction with Large Language Models.

Its purpose is to isolate AI providers from the rest of Hyperium.

Agents should never communicate directly with an AI provider.

---

# Responsibilities

The LLM Layer is responsible for:

- prompt execution
- model selection
- structured output
- retries
- validation
- streaming
- tool calling
- provider abstraction

The LLM Layer does not contain consulting knowledge.

---

# Architecture

```
Agent

↓

LLM Service

↓

Provider

↓

AI Model
```

Agents only know the LLM Service.

The LLM Service knows the Provider.

The Provider communicates with the actual model.

---

# Provider Independence

Hyperium should support multiple providers.

Examples include:

- Ollama
- OpenAI
- Anthropic
- Azure OpenAI
- Local models

Changing provider should not require Agent modifications.

---

# Prompt Management

Prompts belong to Agents.

Prompt execution belongs to the LLM Layer.

This separates consulting knowledge from AI implementation.

---

# Structured Output

Whenever possible, Hyperium should request structured output instead of free text.

Preferred formats include:

- JSON
- JSON Schema
- Typed Objects

Structured output improves reliability and reduces parsing errors.

---

# Validation

The LLM Layer validates responses before returning them.

Examples include:

- JSON validation
- schema validation
- required fields
- retry policies

Invalid responses should never reach the Agent.

---

# Model Selection

Different tasks may require different models.

Examples:

- reasoning
- coding
- summarisation
- reviewing

Model selection should remain configurable.

Agents should not know which model is being used.

---

# Future Capabilities

Future versions may support:

- multi-model routing
- model benchmarking
- automatic model selection
- cost optimisation
- response caching
- prompt versioning

---

# Guiding Principle

Agents perform consultancy work.

The LLM Layer performs AI communication.

The separation between both should remain strict.