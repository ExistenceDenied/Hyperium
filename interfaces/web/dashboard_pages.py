"""
The home screen: one view of what the system is doing and what needs you.

With tasks launching from a queue, schedules firing on a clock, and a reviewer
adding its own work, activity happens while you are away. This page is where
that becomes visible — counts, what is waiting on you, and what just happened.
"""

from __future__ import annotations

from interfaces.web.layout import esc, page
from interfaces.web.task_pages import _pill

_COUNT_LABELS = [
    ("awaiting approval", "Awaiting you", "bad"),
    ("running", "Running", "await"),
    ("queued", "Queued", "draft"),
    ("completed", "Completed", "ok"),
    ("failed", "Failed", "bad"),
]


def _counts_row(counts: dict) -> str:
    cards = []
    for key, label, kind in _COUNT_LABELS:
        number = counts.get(key, 0)
        cards.append(
            "<div class='card' style='flex:1;min-width:120px;text-align:center'>"
            f"<div style='font-size:30px;font-weight:700'>{number}</div>"
            f"<div class='pill {kind}'>{label}</div></div>"
        )
    return "<div class='row' style='align-items:stretch'>" + "".join(cards) + "</div>"


def _attention(attention) -> str:
    if not attention:
        return ""
    items = "".join(
        f"<li><a href='/tasks/{task_id}'>{esc(prompt[:80])}</a></li>"
        for task_id, prompt in attention
    )
    return (
        "<div class='banner'><h3 style='margin-top:0'>Waiting for you</h3>"
        f"<ul style='margin:0'>{items}</ul></div>"
    )


def _recent_tasks(views) -> str:
    if not views:
        return "<p class='muted small'>No tasks yet.</p>"
    rows = "".join(
        f"<tr><td>{_pill(view.status)}</td>"
        f"<td><a href='/tasks/{view.id}'>"
        + esc(view.prompt[:80] + ("…" if len(view.prompt) > 80 else ""))
        + "</a></td></tr>"
        for view in views
    )
    return (
        "<table><thead><tr><th style='width:150px'>Status</th>"
        f"<th>Task</th></tr></thead><tbody>{rows}</tbody></table>"
    )


def _recent_alerts(alerts) -> str:
    if not alerts:
        return "<p class='muted small'>No alerts yet.</p>"
    rows = []
    for note in alerts:
        dot = "" if note.read else "● "
        when = note.at.strftime("%m-%d %H:%M")
        text = esc(note.text)
        body = f"<a href='{esc(note.link)}'>{text}</a>" if note.link else text
        rows.append(
            f"<li>{dot}{body} <span class='small muted'>{when}</span></li>"
        )
    return f"<ul>{''.join(rows)}</ul>"


def dashboard(summary) -> str:
    schedules = summary["schedules"]
    body = (
        "<h1>Dashboard</h1>"
        "<p class='muted'>What the system is doing, and what needs you. It runs "
        "tasks from the queue and on a schedule on its own — this is where that "
        "surfaces.</p>"
        + _attention(summary["attention"])
        + _counts_row(summary["counts"])
        + "<div class='row'><h2>Recent tasks</h2>"
        "<a class='btn' href='/tasks'>All tasks</a></div>"
        + _recent_tasks(summary["recent_tasks"])
        + "<div class='row'><h2>Recent alerts</h2>"
        "<a class='btn' href='/notifications'>All alerts</a></div>"
        + _recent_alerts(summary["alerts"])
        + "<div class='row'><h2>Schedules</h2>"
        "<a class='btn' href='/tasks'>Manage</a></div>"
        f"<p class='muted small'>{schedules['active']} running on a clock, "
        f"{schedules['paused']} paused.</p>"
    )
    return page("Dashboard", body, section="dashboard")
