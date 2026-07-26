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


_PRIORITY_PILL = {"high": "bad", "medium": "await", "low": "draft"}


def _pill(status: str) -> str:
    kind = _STATUS_PILL.get(status, "draft")
    return f"<span class='pill {kind}'>{esc(status)}</span>"


def _priority_pill(priority: str) -> str:
    kind = _PRIORITY_PILL.get(priority, "draft")
    return f"<span class='pill {kind}'>{esc(priority)}</span>"


def _duration(view) -> str:
    if view.duration is None:
        return ""
    seconds = int(view.duration)
    return f"{seconds}s" if seconds < 60 else f"{seconds // 60}m {seconds % 60}s"


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
            f"<td>{_priority_pill(view.priority)}</td>"
            f"<td><a href='/tasks/{view.id}'>{prompt}</a></td></tr>"
        )

    body = (
        "<div class='row'><h1>Tasks</h1>" + new + "</div>"
        "<table><thead><tr><th style='width:130px'>Status</th>"
        "<th style='width:90px'>Priority</th>"
        "<th>Task</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )

    return page("Tasks", body, section="tasks")


def new_task() -> str:
    body = (
        "<h1>New task</h1>"
        "<p class='muted'>Describe the job, and attach any files the agent "
        "should use. It can read and write files and reach the web, and will "
        "ask you before it changes or sends anything.</p>"
        "<form method='post' action='/tasks' enctype='multipart/form-data'>"
        "<label>Task"
        "<textarea name='prompt' rows='4' required placeholder='e.g. Turn the "
        "prices in the attached file into a quote in quote.xlsx.'></textarea>"
        "</label>"
        "<label>Priority"
        "<select name='priority'>"
        "<option value='low'>Low</option>"
        "<option value='medium' selected>Medium</option>"
        "<option value='high'>High</option>"
        "</select></label>"
        "<label>Attach files (optional)"
        "<input type='file' name='files' multiple></label>"
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


def _files(view) -> str:
    if view.files:
        items = "".join(
            f"<li><a href='/tasks/{view.id}/file/{esc(name)}'>{esc(name)}</a>"
            f" <span class='small muted'>{size} bytes</span></li>"
            for name, size in view.files
        )
        listing = f"<ul>{items}</ul>"
    else:
        listing = "<p class='muted small'>No files yet.</p>"

    upload = (
        f"<form method='post' action='/tasks/{view.id}/upload' "
        "enctype='multipart/form-data' style='margin-top:8px'>"
        "<input type='file' name='files' multiple>"
        "<div class='actions'><button type='submit'>Upload files</button>"
        "</div></form>"
    )

    return (
        "<h3>Files</h3>"
        "<p class='muted small'>The agent's inputs and outputs for this task. "
        "Upload files here and refer to them by name; downloads are the files "
        "it produced.</p>" + listing + upload
    )


def _notes(view) -> str:
    if view.notes:
        items = "".join(
            f"<li>{esc(note.text)} "
            f"<span class='small muted'>{note.at.strftime('%Y-%m-%d %H:%M')}</span>"
            "</li>"
            for note in view.notes
        )
        listing = f"<ul>{items}</ul>"
    else:
        listing = "<p class='muted small'>No notes yet.</p>"

    form = (
        f"<form method='post' action='/tasks/{view.id}/note' style='margin-top:8px'>"
        "<input name='note' placeholder='Add a note or comment…' required>"
        "<div class='actions'><button type='submit'>Add note</button></div></form>"
    )

    return "<h3>Notes</h3>" + listing + form


def task_detail(view) -> str:
    took = (
        f" <span class='small muted'>took {_duration(view)}</span>"
        if view.duration
        else ""
    )

    parts = [
        "<div class='row'><h1>Task</h1>"
        "<a class='btn' href='/tasks'>All tasks</a></div>",
        f"<div class='card'><div class='row'><div>{_pill(view.status)} "
        f"{_priority_pill(view.priority)}{took}</div>"
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

    parts.append(_files(view))

    if view.output:
        parts.append("<h3>Result</h3>")
        parts.append(f"<div class='card doc'>{render(view.output)}</div>")

    parts.append(_notes(view))
    parts.append(_steps(view))

    # Refresh only while there is something to wait for.
    return page("Task", "".join(parts), refresh=view.active, section="tasks")
