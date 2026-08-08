# ADR-006: The Plan Owns Its Governance

> Version: 1.0
> Status: **Accepted**
> Amends [ADR-004](ADR-004-execution-model.md) and
> [ADR-005](ADR-005-methodology-driven-planning.md).
> Reconciles `core/methodologies/` with
> [ADR-002](ADR-002-bounded-contexts.md).

---

# Context

A hostile review of the architecture, run deliberately against work the author
had just completed, found that several rules the documentation asserts were
not true of the code. Three mattered.

**The documentation was unenforced.** Around thirty invariants are stated
across the architecture docs — *"dependencies point inward"*, *"business
contexts must never depend directly on AI providers"*, *"analysis never
creates execution plans"* — and **nothing checked any of them**. That is the
root cause rather than a symptom: every other defect below is something a
cheap automated check would have caught the day it was introduced.

**The plan was laundered through the analysis.**
[ADR-005](ADR-005-methodology-driven-planning.md) demoted the analysis from
planner to advisor, but the implementation wrote the methodology's work
breakdown *back into* `AnalysisResult`, and everything downstream — the
project, both interfaces, the on-disk schema — read the engagement's
deliverables from there. `ADR-002`'s *"Analysis never creates execution
plans"* was therefore literally false in the one place it mattered.

**Governance could be edited out from under a running engagement.** Quality
gates were resolved from the methodology registry at read time. Renaming or
deleting a methodology file silently opened every gate on every engagement in
flight, with no message. This contradicted the platform's own rule, stated in
[12-interfaces.md](12-interfaces.md), that it must never hide what it cannot
read.

A fourth, structural: `core.execution` and `core.methodologies` imported each
other, so neither could be understood or tested alone.

---

# Decision

## 1. Architecture invariants are tests, not prose

`tests/test_architecture.py` asserts the layering rule, the no-provider rule,
that no model reaches governance code, that no two packages import each other,
and that the capability catalogue and the prompt library agree.

They are deliberately crude — they read import statements, not semantics.
That is enough to catch the drift that actually happens. The circular
dependency above was found by the first run of the first such test.

**A rule that is not checked is a wish.** Any future invariant added to these
documents should arrive with the test that enforces it.

## 2. The plan owns the work

`ExecutionPlan` holds the deliverables. `AnalysisResult` no longer has the
field at all — not emptied, removed — so the rule cannot be violated by
accident again. `Project.deliverables` reads from the plan.

## 3. The plan owns its stages and its gates

`ExecutionPlan` carries `StagePlan` objects, each with a copy of the
`QualityGate` the engagement was planned under. The registry is consulted at
*planning* time and never again.

An engagement is therefore held to the rules it was planned with, and those
rules survive the methodology being edited, renamed or deleted. This also
removes the persistence layer's dependency on the methodology registry
entirely.

## 4. Gates evaluate state, not entities

`QualityGate.evaluate` takes `DeliverableState` — a small frozen record of
key, approval, status and content — rather than a `Deliverable`. This breaks
the package cycle and makes the gate trivially testable without constructing
an engagement.

## 5. Silence is not an acceptable failure mode

Four paths that previously degraded quietly now raise: planning without a
methodology, planning without a mission, a plan that yields zero activities,
and loading a saved plan that references work no deliverable provides.

An unknown capability key is now rejected when the methodology is **loaded**,
naming the file and the valid set, rather than surfacing as a bare `KeyError`
midway through planning. That restores the guarantee
[ADR-005](ADR-005-methodology-driven-planning.md) claimed but did not deliver.

## 6. Approval is a service operation

`ProjectService.approve` and `.request_changes` own the governance act. Both
interfaces call them.

This was not theoretical tidiness: the CLI and the web review UI had each
implemented approval themselves and had **drifted**. The web required feedback
on rejection; the CLI did not. Two interfaces, two different governance
behaviours, on the most sensitive operation in the platform.

## 7. Saved engagements are migrated, not refused

`infrastructure/persistence/migrations.py` upgrades an older file one version
at a time. A schema bump no longer costs anyone their work.

Migrations never invent governance. Upgrading a version 3 engagement cannot
recover the quality gates, because that version stored only the methodology
key and the gates lived in the registry. Reconstructing them from whatever the
registry holds *today* would hold an engagement to rules it was never planned
under, so the stages are left empty and the loss is logged. **Absent and
reported beats invented.**

A test asserts every version below the current one has a migration, so a
future bump without one fails the build.

## 8. `core/methodologies/` is a bounded context

[ADR-002](ADR-002-bounded-contexts.md) assigned Methodologies to the
*Knowledge* context, which does not exist. Rather than place authored
methodologies inside an unbuilt context, Methodologies is recognised as a
context in its own right:

> **Methodologies** — owns Methodology, Stage, DeliverableTemplate,
> ActivityTemplate, Technique, QualityGate. Authored, versioned, immutable at
> runtime. Depended on by Planning. Depends on nothing.

Knowledge, when it is built, will own lessons learned, patterns and reusable
examples — the things extracted *from* engagements — not the methodology that
directs them. These were conflated in ADR-002 and are separate concerns.

---

# Consequences

**Positive**

- Every invariant named in decision 1 now fails the build when broken.
- Governance cannot change under a running engagement.
- A new domain field cannot silently fail to persist: a reflection test over
  each dataclass fails until the serializer maps it.
- Older engagements open.
- `core.methodologies` can be tested and reasoned about alone.

**Negative**

- Schema 4, and a fourth migration to maintain. The chain will grow.
- A version 3 engagement resumes without stage gates. This is honest, but it
  is a real loss for anyone upgrading mid-engagement.
- The fitness functions read imports, not behaviour. They would not catch a
  layering violation made through a runtime lookup.

**Not addressed** — carried forward deliberately:

- `isinstance(resource, AIResource)` at four sites still decides who may
  execute. A fifth resource type requires editing the engine.
- The capability catalogue is hardcoded Python, so a methodology needing a
  ninth capability still requires a code change — narrowing but not closing
  the gap in [ADR-005](ADR-005-methodology-driven-planning.md) decision 3.
- `methodologies` and `techniques` are passed as untyped duck-typed seams.
- `core/interfaces/` (ports) and `interfaces/` (adapters) share a name while
  meaning opposite ends of the dependency arrow.

---

# Alternatives considered

**Resolve gates from the registry, but fail loudly when the methodology is
missing.** Simpler, and it was the first fix attempted. Rejected because it
only converts silent governance loss into a hard failure — an engagement would
become unopenable because someone renamed a file. Copying the gates into the
plan solves the ownership question instead of the symptom.

**Keep deliverables on `AnalysisResult` and add a comment.** Rejected: the
review found this precisely *because* it was a comment away from correct and
nothing enforced it.

**Add `import-linter` or a similar tool.** Reasonable, and worth revisiting.
Rejected for now because the checks needed are few and specific, and a
hand-written test states the invariant in the vocabulary of the architecture
rather than a config file's.

**Amend ADR-002 in place** rather than writing this ADR. Rejected because an
accepted ADR is a record of a decision at a point in time. Superseding it in a
new document preserves why the original call was made.
