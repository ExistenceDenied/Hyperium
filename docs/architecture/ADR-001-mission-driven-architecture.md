# ADR-001 – Mission Driven Architecture

## Status

Accepted

## Context

Traditional AI platforms are prompt-driven.

The user provides a prompt to an AI model and receives a response.

Hyperium aims to be fundamentally different.

Hyperium is not a prompt execution engine.
It is an Operating System for Professional Services.

Professional work starts with a mission, not with a prompt.

A mission represents a business objective that should be achieved.
The software determines how that objective can best be accomplished.

## Decision

Mission is the highest-level business concept in Hyperium.

Every execution starts with a Mission.

A Mission must first be analysed before a project can be created.

The execution pipeline becomes:

Mission
→ Mission Analysis
→ Execution Strategy
→ Project
→ Execution
→ Knowledge

Prompts are considered implementation details and are not part of the core domain model.

## Consequences

The domain model is centred around business concepts instead of AI concepts.

Planning becomes reusable across disciplines.

AI providers become interchangeable implementation details.

Hyperium can support human resources, AI resources and external tools using the same planning model.

## Principles

Business before Technology

Understand before Planning

Planning before Execution

Knowledge after Execution

Mission over Prompt