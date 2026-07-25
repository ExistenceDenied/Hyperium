"""
Pages for the direct-task path: start a task, watch it, approve its actions.

The counterpart to the engagement views. Where an engagement runs a whole
methodology, a task is a single ad-hoc instruction carried out by the agent —
and this is where a person approves any action it wants to take.
"""

from __future__ import annotations

from interfaces.web.layout import esc, page
from interfaces.web.markdown import render

_STATUS_PILL = {
    "running": "await",
    "awaiting approval": "await",
    "completed": "ok",
    "failed": "bad",
    "max_iterations": "bad",
}


def _pill(status: str) -> str:
    kind = _STATUS_PILL.get(status, "draft")
    return f"<span class='pill {kind}'>{esc(status)}</span>"


def tasks_index(views) -> str:
    new = "<a class='btn primary' href='/tasks/new'>New task</a>"

    if not views:
        body = (
            "<div class='row'><h1>Tasks</h1>" + new + "</div>"
            "<div class='empty'>No tasks yet. Give the agent something to do.</div>"
        )
        return page("Tasks", body, section="tasks")

    rows = []
    for view in views:
        prompt = esc(view.prompt[:90] + ("…" if len(view.prompt) > 90 else ""))
        rows.append(
            f"<tr><td>{_pill(view.status)}</td>"
            f"<td><a href='/tasks/{view.id}'>{prompt}</a></td></tr>"
        )

    body = (
        "<div class='row'><h1>Tasks</h1>" + new + "</div>"
        "<table><thead><tr><th style='width:150px'>Status</th>"
        "<th>Task</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )

    return page("Tasks", body, section="tasks")


def new_task() -> str:
    body = (
        "<h1>New task</h1>"
        "<p class='muted'>The agent reads files and the web on its own. If you "
        "allow writes, it can change files too — and will ask you before each "
        "one.</p>"
        "<form method='post' action='/tasks'>"
        "<label>Task"
        "<textarea name='prompt' rows='4' required placeholder='e.g. Summarise "
        "the latest deliverable and list open risks.'></textarea></label>"
        "<label style='display:flex;align-items:center;gap:8px;font-weight:400'>"
        "<input type='checkbox' name='allow_writes' value='1' "
        "style='width:auto'> Allow the agent to change files (with approval)"
        "</label>"
        "<div class='actions'><button class='primary' type='submit'>"
        "Start</button>"
        "<a class='btn' href='/tasks'>Cancel</a></div>"
        "</form>"
    )

    return page("New task", body, section="tasks")


def _approval_card(view) -> str:
    request = view.pending

    return (
        "<div class='banner'>"
        "<h3 style='margin-top:0'>Approval needed</h3>"
        f"<p>The agent wants to: <strong>{esc(request.preview)}</strong></p>"
        f"<form method='post' action='/tasks/{view.id}/approve'>"
        "<div class='actions'>"
        "<button class='primary' name='decision' value='approve' type='submit'>"
        "Approve</button>"
        "<button class='danger' name='decision' value='reject' type='submit'>"
        "Reject</button>"
        "</div></form></div>"
    )


def _steps(view) -> str:
    if not view.steps:
        return ""

    rows = []
    for step in view.steps:
        preview = esc(step.result.replace("\n", " ")[:120])
        rows.append(
            f"<tr><td><code>{esc(step.tool)}</code></td>"
            f"<td class='small muted'>{preview}</td></tr>"
        )

    return (
        "<h3>Steps</h3><table><thead><tr><th style='width:180px'>Tool</th>"
        "<th>Result</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def task_detail(view) -> str:
    parts = [
        "<div class='row'><h1>Task</h1>"
        "<a class='btn' href='/tasks'>All tasks</a></div>",
        f"<div class='card'><div class='row'>{_pill(view.status)}"
        f"<form method='post' action='/tasks/{view.id}/rerun' style='margin:0'>"
        "<button type='submit'>Run again</button></form></div>"
        f"<p style='margin-bottom:0'>{esc(view.prompt)}</p></div>",
    ]

    if view.pending is not None:
        parts.append(_approval_card(view))

    if view.active and view.pending is None:
        parts.append(
            "<p class='muted'>Working… this page refreshes on its own.</p>"
        )

    if view.error:
        parts.append(f"<div class='banner bad'>{esc(view.error)}</div>")

    parts.append(_steps(view))

    if view.output:
        parts.append("<h3>Result</h3>")
        parts.append(f"<div class='card doc'>{render(view.output)}</div>")

    # Refresh only while there is something to wait for.
    return page("Task", "".join(parts), refresh=view.active, section="tasks")
