# Hyperium LLM Layer

> Version: 1.0

---

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