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
    "queued": "draft",
    "pending": "draft",
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


def _backlog_section(missions) -> str:
    new = "<a class='btn' href='/missions/new'>New mission</a>"

    if not missions:
        listing = "<p class='muted small'>No missions in the backlog.</p>"
    else:
        rows = "".join(
            f"<tr><td><span class='pill draft'>{esc(mission.status.value)}</span></td>"
            f"<td class='muted small'>{esc(mission.priority.name.lower())}</td>"
            f"<td><a href='/missions/{mission.id}'>{esc(mission.title)}</a></td></tr>"
            for mission in missions
        )
        listing = (
            "<table><thead><tr><th style='width:130px'>Status</th>"
            "<th style='width:90px'>Priority</th><th>Mission</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )

    return (
        "<div class='row' style='margin-top:28px'><h2>Backlog</h2>" + new + "</div>"
        "<p class='muted small'>Larger pieces of work. A mission becomes a full "
        "methodology-driven engagement when you launch it.</p>" + listing
    )


def _schedules_section(schedules) -> str:
    new = "<a class='btn' href='/schedules/new'>New schedule</a>"

    if not schedules:
        listing = "<p class='muted small'>Nothing runs on a clock yet.</p>"
    else:
        rows = []
        for schedule in schedules:
            state = "on" if schedule.enabled else "off"
            kind = "ok" if schedule.enabled else "draft"
            toggle = "Pause" if schedule.enabled else "Resume"
            rows.append(
                f"<tr><td><span class='pill {kind}'>{state}</span></td>"
                f"<td class='muted small'>{esc(schedule.cadence)}</td>"
                f"<td>{esc(schedule.prompt[:90])}"
                f"{'…' if len(schedule.prompt) > 90 else ''}</td>"
                "<td style='white-space:nowrap'>"
                f"<form method='post' action='/schedules/{schedule.id}/toggle' "
                "style='display:inline;margin:0'>"
                f"<button type='submit'>{toggle}</button></form> "
                f"<form method='post' action='/schedules/{schedule.id}/delete' "
                "style='display:inline;margin:0'>"
                "<button class='danger' type='submit'>Delete</button>"
                "</form></td></tr>"
            )
        listing = (
            "<table><thead><tr><th style='width:70px'>State</th>"
            "<th style='width:90px'>Runs</th><th>Task</th>"
            "<th style='width:160px'></th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    return (
        "<div class='row' style='margin-top:28px'><h2>Schedules</h2>" + new + "</div>"
        "<p class='muted small'>Standing tasks the system runs on a clock. When "
        "one is due it goes on the queue and the worker runs it — so work happens "
        "without you starting it.</p>" + listing
    )


def tasks_index(views, missions=(), schedules=()) -> str:
    new = "<a class='btn primary' href='/tasks/new'>New task</a>"

    if views:
        rows = "".join(
            f"<tr><td>{_pill(view.status)}</td>"
            f"<td>{_priority_pill(view.priority)}</td>"
            "<td><a href='/tasks/"
            f"{view.id}'>"
            + esc(view.prompt[:90] + ("…" if len(view.prompt) > 90 else ""))
            + "</a></td></tr>"
            for view in views
        )
        tasks = (
            "<table><thead><tr><th style='width:130px'>Status</th>"
            "<th style='width:90px'>Priority</th>"
            f"<th>Task</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    else:
        tasks = "<div class='empty'>No tasks yet. Give the agent a quick job.</div>"

    body = (
        "<div class='row'><h1>Tasks</h1>" + new + "</div>"
        + tasks
        + _schedules_section(list(schedules or []))
        + _backlog_section(list(missions or []))
    )

    return page("Tasks", body, section="tasks")


def _options(items) -> str:
    return "".join(
        f"<option value='{esc(item.key)}'>{esc(item.name)}</option>"
        for item in items
    )


def new_task(techniques=(), methodologies=()) -> str:
    body = (
        "<h1>New task</h1>"
        "<p class='muted'>Describe the job, and attach any files the agent "
        "should use. Optionally pick a technique or methodology for it to "
        "follow. It can read and write files and reach the web, and will ask "
        "you before it changes or sends anything.</p>"
        "<form method='post' action='/tasks' enctype='multipart/form-data'>"
        "<label>Task"
        "<textarea name='prompt' rows='4' required placeholder='e.g. Turn the "
        "prices in the attached file into a quote in quote.xlsx.'></textarea>"
        "</label>"
        "<div class='grid2'>"
        "<label>Priority"
        "<select name='priority'>"
        "<option value='low'>Low</option>"
        "<option value='medium' selected>Medium</option>"
        "<option value='high'>High</option>"
        "</select></label>"
        "<label>Technique (optional)"
        "<select name='technique'><option value=''>— none —</option>"
        + _options(techniques)
        + "</select></label>"
        "</div>"
        "<label>Methodology (optional)"
        "<select name='methodology'><option value=''>— none —</option>"
        + _options(methodologies)
        + "</select></label>"
        "<label>Attach files (optional)"
        "<input type='file' name='files' multiple></label>"
        "<label style='display:flex;gap:8px;font-weight:400;margin-top:10px'>"
        "<input type='checkbox' name='queue' value='1' style='width:auto'> "
        "Add to the queue instead of starting now</label>"
        "<div class='actions'><button class='primary' type='submit'>"
        "Start</button>"
        "<a class='btn' href='/tasks'>Cancel</a></div>"
        "</form>"
    )

    return page("New task", body, section="tasks")


def new_schedule(techniques=(), methodologies=()) -> str:
    body = (
        "<h1>New schedule</h1>"
        "<p class='muted'>A task the system runs on a clock. Each time it is "
        "due, it is added to the queue and the worker runs it — using your "
        "business memory, and the technique or methodology you pick.</p>"
        "<form method='post' action='/schedules'>"
        "<label>Task"
        "<textarea name='prompt' rows='4' required placeholder='e.g. Summarise "
        "yesterday&#39;s new invoices into invoices.xlsx.'></textarea></label>"
        "<div class='grid2'>"
        "<label>Runs"
        "<select name='every_hours'>"
        "<option value='1'>Hourly</option>"
        "<option value='24' selected>Daily</option>"
        "<option value='168'>Weekly</option>"
        "</select></label>"
        "<label>Priority"
        "<select name='priority'>"
        "<option value='low'>Low</option>"
        "<option value='medium' selected>Medium</option>"
        "<option value='high'>High</option>"
        "</select></label>"
        "</div>"
        "<div class='grid2'>"
        "<label>Technique (optional)"
        "<select name='technique'><option value=''>— none —</option>"
        + _options(techniques)
        + "</select></label>"
        "<label>Methodology (optional)"
        "<select name='methodology'><option value=''>— none —</option>"
        + _options(methodologies)
        + "</select></label>"
        "</div>"
        "<div class='actions'><button class='primary' type='submit'>"
        "Create schedule</button>"
        "<a class='btn' href='/tasks'>Cancel</a></div>"
        "</form>"
    )

    return page("New schedule", body, section="tasks")


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

    approach = ""
    if view.technique:
        approach += (
            f" <span class='small muted'>· technique: {esc(view.technique)}</span>"
        )
    if view.methodology:
        approach += (
            f" <span class='small muted'>· methodology: {esc(view.methodology)}</span>"
        )

    parts = [
        "<div class='row'><h1>Task</h1>"
        "<a class='btn' href='/tasks'>All tasks</a></div>",
        f"<div class='card'><div class='row'><div>{_pill(view.status)} "
        f"{_priority_pill(view.priority)}{took}{approach}</div>"
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

    if view.status == "completed":
        parts.append(
            f"<form method='post' action='/tasks/{view.id}/improve' "
            "style='margin-top:12px'><button type='submit'>"
            "Suggest improvement tasks</button></form>"
        )

    parts.append(_notes(view))
    parts.append(_steps(view))

    # Refresh only while there is something to wait for.
    return page("Task", "".join(parts), refresh=view.active, section="tasks")
