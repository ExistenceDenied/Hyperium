# Interfaces

> Version: 2.0

---

# Purpose

An interface is how a human reaches Hyperium.

Until this document existed the architecture was silent on the subject: there
was no mention of a command line, a web interface, or any delivery channel
anywhere in the documentation, even after both had been built. That silence is
how interface layers quietly accumulate business rules.

---

# The rule

**An interface is an adapter. It contains no business logic.**

Every interface is a caller of the application services — `ProjectService`,
`MissionBacklogService` — on equal footing with every other interface. None of
them is privileged, and none of them may decide anything the domain should
decide.

```
Human ──> Interface (CLI, Web) ──> Application Services ──> Domain
```

An interface may:

- read domain objects and present them
- translate user input into a service call
- format, render, paginate and style
- decide what to *show*

An interface may **not**:

- decide whether a deliverable may be approved
- decide whether an activity is ready to run
- construct an execution plan or mutate one
- validate a mission
- write to the artifact store or the repository directly, other than through a
  service that owns that decision

The test: **if two interfaces would have to implement the same rule, that rule
belongs in the domain.** When the web interface needed to know whether a
deliverable was awaiting approval, it asked `Deliverable.status`; it did not
re-derive the condition.

---

# Delivered interfaces

## Command line — `interfaces/cli.py`

The complete lifecycle: mission backlog CRUD, launch, resume, submit, approve,
reject, list, show, serve. It is the reference interface, and anything the web
interface can do the CLI can do.

## Web — `interfaces/web/`

A local, single-user interface covering the whole lifecycle: capture a mission,
refine it, launch it, review what comes back, and submit work assigned to a
person.

| Module | Responsibility |
|---|---|
| `server.py` | Routing, request handling, background work, origin checking |
| `layout.py` | Shared chrome: styles, escaping, navigation |
| `pages.py` | Engagements, deliverables, diffs |
| `backlog_pages.py` | Mission backlog and the mission form |
| `methodology_pages.py` | Read-only methodology and technique browser |
| `markdown.py` | Markdown to safe HTML |
| `diff.py` | Version comparison |

**Version 1 of this document said the opposite** — that mission authoring must
stay on the command line, "because a second way to create missions is a second
thing to keep correct". That reasoning was right, and it is what made the
change safe once the condition was met: since
[ADR-006](ADR-006-plan-owns-its-governance.md) every governance decision lives
in `ProjectService` or `MissionBacklogService`, and both interfaces call them.
Neither reimplements anything.

The parity is asserted, not assumed. `tests/test_web_backlog.py` and
`tests/test_cli.py` cover the same operations against the same services, and
the drift that prompted ADR-006 — the web requiring rejection feedback while
the CLI did not — has a regression test in both.

**Methodologies remain read-only in the browser.** They are the platform's
most important asset, authored as reviewed, version-controlled JSON. Putting
them behind a textarea would trade that for convenience.

---

# Constraints

## No web framework

Hyperium's only runtime dependency is an LLM client. A review tool is not a
sufficient reason to add a framework, so the web interface is built on
`http.server` from the standard library. If the interface ever needs
multi-user access, authentication or an API, that decision should be taken
explicitly in an ADR rather than arriving as a dependency.

## Untrusted content

**Deliverable content is written by a language model and is untrusted input.**
It is rendered into a page, so it is an injection surface.

`markdown.py` escapes every line *before* applying any markup, restricts link
targets to `http`/`https`, and never emits raw input. Responses carry a
restrictive `Content-Security-Policy` and `X-Content-Type-Options: nosniff`.
Any future renderer must preserve these properties.

## Local by default, and defended anyway

The server binds to `127.0.0.1` and has **no authentication**. Binding
elsewhere prints a warning. Multi-user access, identity and an audit trail are
4.0 concerns and must not be improvised in the interface layer.

No authentication makes **cross-site request forgery** the real exposure: any
page open in the same browser can post to localhost. Every state-changing
request is therefore checked — the `Origin` (or failing that, `Referer`) must
match the `Host` it was sent to, or it is refused with 403.

An earlier version compared against a set of origins computed at startup from
the configured port. That was wrong in a way worth recording: binding to port
0 produced a server that refused every one of its own posts. The `Host` header
is the address the browser actually used, and is correct however the server
was bound.

## Long-running work

Execution can take minutes. The web interface runs it on a background thread
and reports progress, rather than holding a request open. A failure is shown
on the page; it is never swallowed.

## Never hide what you cannot read

If an engagement cannot be loaded — a schema mismatch, a corrupt file — the
interface says so, naming the engagement and the reason. Silently omitting it
would leave a reviewer unable to distinguish "does not exist" from "broken".

---

# Relationship to the architecture

Interfaces sit outside the bounded contexts defined in
[ADR-002](ADR-002-bounded-contexts.md) and depend inward only, consistent with
the dependency rule in [09-extensibility.md](09-extensibility.md):

```
Interfaces ──> Application ──> Domain
     │
     └──> Infrastructure (composition root only)
```

Only the composition root inside an interface — `build_context`,
`build_backlog` — may name concrete infrastructure. Everything past that point
works against interfaces such as `LLMProvider` and `ArtifactStore`.

---

# Adding an interface

1. Call the existing application services. If the service you need does not
   exist, add it to the application layer — not to the interface.
2. Keep the composition root in one place.
3. Escape untrusted content.
4. Add tests that exercise the adapter directly, without a network or a live
   model.
