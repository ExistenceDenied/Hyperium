"""
Mission backlog views.

Every decision here is asked of `MissionBacklogService` — whether a mission is
complete, whether it may be edited, what may be deleted. These functions only
choose what to show.
"""

from __future__ import annotations

from core.missions.mission_priority import MissionPriority
from core.missions.mission_status import MissionStatus
from interfaces.web.layout import esc, page

_STATUS_CLASS = {
    MissionStatus.DRAFT: "draft",
    MissionStatus.READY: "ok",
    MissionStatus.LAUNCHED: "await",
    MissionStatus.ARCHIVED: "draft",
}


def status_pill(mission) -> str:
    css = _STATUS_CLASS.get(mission.status, "draft")

    return f"<span class='pill {css}'>{esc(mission.status.value)}</span>"


def backlog(missions, show_archived: bool = False, launching=()) -> str:
    body = [
        "<div class='row'><h1>Mission backlog</h1>"
        "<a class='btn primary' href='/missions/new'>New mission</a></div>",
        "<p class='muted'>Ordered by priority, then by age. A mission may be "
        "captured incomplete and refined later; it is validated when you "
        "launch it.</p>",
    ]

    if not missions:
        body.append(
            "<div class='empty'><p>Nothing in the backlog yet.</p>"
            "<a class='btn primary' href='/missions/new'>Add the first "
            "mission</a></div>"
        )
        return page("Backlog", "".join(body), section="backlog")

    body.append(
        "<table><thead><tr><th>Priority</th><th>Status</th><th>Mission</th>"
        "<th>Methodology</th><th></th></tr></thead><tbody>"
    )

    for mission in missions:
        flag = (
            ""
            if mission.is_complete
            else " <span class='muted small'>(needs a success criterion)</span>"
        )
        busy = mission.id in launching

        if busy:
            action = "<span class='muted small'>launching…</span>"
        elif mission.is_launched:
            action = (
                f"<a href='/engagement/{mission.project_id}'>Engagement →</a>"
            )
        else:
            action = f"<a href='/missions/{mission.id}'>Open</a>"

        body.append(
            f"<tr><td>{esc(mission.priority.name)}</td>"
            f"<td>{status_pill(mission)}</td>"
            f"<td><a href='/missions/{mission.id}'>{esc(mission.title)}</a>"
            f"{flag}</td>"
            f"<td class='muted small'>{esc(mission.methodology or '—')}</td>"
            f"<td>{action}</td></tr>"
        )

    body.append("</tbody></table>")

    body.append(
        f"<p class='small'><a href='/missions?all={'0' if show_archived else '1'}'>"
        f"{'Hide' if show_archived else 'Show'} archived</a></p>"
    )

    return page("Backlog", "".join(body), refresh=bool(launching), section="backlog")


def mission_detail(
    mission,
    methodologies,
    launching: bool = False,
    error: str = "",
) -> str:
    body = [
        "<p><a href='/missions'>← Backlog</a></p>",
        f"<h1>{esc(mission.title)}</h1>",
        f"<p>{status_pill(mission)} "
        f"<span class='pill'>{esc(mission.priority.name)}</span> "
        f"<span class='muted small'>{esc(mission.id)}</span></p>",
        f"<div class='card'><p>{esc(mission.objective.description)}</p></div>",
    ]

    if error:
        body.append(
            f"<div class='banner bad'><strong>Could not launch.</strong><br>"
            f"{esc(error)}</div>"
        )

    if launching:
        body.append(
            "<div class='banner'>Launching… Hyperium is planning and running "
            "the first stage. This page refreshes automatically.</div>"
        )

    body.append(_facts(mission))

    if mission.is_launched:
        body.append(
            "<div class='actions'>"
            f"<a class='btn primary' href='/engagement/{mission.project_id}'>"
            "Open the engagement</a></div>"
            "<p class='muted small'>A launched mission is frozen: the "
            "engagement holds its own copy, and editing this would let the "
            "two drift apart.</p>"
        )
    elif not launching:
        body.append(_launch_form(mission, methodologies))
        body.append(_manage_form(mission))

    return page(
        mission.title,
        "".join(body),
        refresh=launching,
        section="backlog",
    )


def _facts(mission) -> str:
    blocks = []

    for label, items in (
        ("Success criteria", [c.description for c in mission.success_criteria]),
        (
            "Constraints",
            [f"[{c.type.name}] {c.description}" for c in mission.constraints],
        ),
        ("Stakeholders", [f"{s.name} — {s.role}" for s in mission.stakeholders]),
    ):
        if items:
            entries = "".join(f"<li>{esc(item)}</li>" for item in items)
            blocks.append(f"<h3>{label}</h3><ul>{entries}</ul>")

    if not mission.is_complete:
        blocks.append(
            "<div class='banner'>This mission has no success criterion, so it "
            "cannot be launched yet. Add one below.</div>"
        )

    return "".join(blocks)


def _launch_form(mission, methodologies) -> str:
    options = ["<option value=''>Let the analysis recommend one</option>"]

    for item in methodologies:
        selected = " selected" if item.key == mission.methodology else ""
        options.append(
            f"<option value='{esc(item.key)}'{selected}>{esc(item.name)} "
            f"({len(item.stages)} stages, {len(item.activities)} activities)"
            f"</option>"
        )

    disabled = "" if mission.is_complete else " disabled"

    return (
        f"<form method='post' action='/missions/{mission.id}/launch'>"
        "<h2>Launch</h2>"
        "<label>Methodology <span class='hint'>— decides what work the "
        "engagement contains</span></label>"
        f"<select name='methodology'>{''.join(options)}</select>"
        "<div class='actions'>"
        f"<button class='primary' type='submit'{disabled}>Launch engagement"
        "</button></div>"
        "</form>"
    )


def _manage_form(mission) -> str:
    archive = (
        "restore" if mission.status is MissionStatus.ARCHIVED else "archive"
    )

    return (
        "<h2>Manage</h2><div class='actions'>"
        f"<a class='btn' href='/missions/{mission.id}/edit'>Edit</a>"
        f"<form method='post' action='/missions/{mission.id}/{archive}'>"
        f"<button type='submit'>{archive.title()}</button></form>"
        f"<form method='post' action='/missions/{mission.id}/delete'>"
        "<button class='danger' type='submit'>Delete</button></form>"
        "</div>"
    )


def mission_form(
    mission=None,
    methodologies=(),
    error: str = "",
    values: dict | None = None,
) -> str:
    """One form for both creating and editing."""
    editing = mission is not None
    values = values or {}

    def value(name, fallback=""):
        if name in values:
            return values[name]
        return fallback

    title = value("title", mission.title if editing else "")
    objective = value(
        "objective", mission.objective.description if editing else ""
    )
    criteria = value(
        "criteria",
        "\n".join(c.description for c in mission.success_criteria)
        if editing
        else "",
    )
    constraints = value(
        "constraints",
        "\n".join(f"{c.type.name}: {c.description}" for c in mission.constraints)
        if editing
        else "",
    )
    chosen = value("methodology", mission.methodology if editing else "")
    priority = value(
        "priority", mission.priority.name if editing else "MEDIUM"
    )

    action = f"/missions/{mission.id}/edit" if editing else "/missions"

    priorities = "".join(
        f"<option value='{item.name}'"
        f"{' selected' if item.name == priority else ''}>"
        f"{item.name.title()}</option>"
        for item in reversed(list(MissionPriority))
    )

    options = ["<option value=''>Decide at launch</option>"]
    for item in methodologies:
        options.append(
            f"<option value='{esc(item.key)}'"
            f"{' selected' if item.key == chosen else ''}>"
            f"{esc(item.name)}</option>"
        )

    banner = (
        f"<div class='banner bad'>{esc(error)}</div>" if error else ""
    )

    return page(
        "Edit mission" if editing else "New mission",
        f"<p><a href='/missions'>← Backlog</a></p>"
        f"<h1>{'Edit mission' if editing else 'New mission'}</h1>"
        f"{banner}"
        f"<form method='post' action='{action}'>"
        "<label>Title</label>"
        f"<input name='title' required value='{esc(title)}'>"
        "<label>Objective <span class='hint'>— what this engagement must "
        "achieve</span></label>"
        f"<textarea name='objective' rows='3' required>{esc(objective)}"
        "</textarea>"
        "<div class='grid2'>"
        f"<div><label>Priority</label><select name='priority'>{priorities}"
        "</select></div>"
        "<div><label>Methodology <span class='hint'>— optional</span></label>"
        f"<select name='methodology'>{''.join(options)}</select></div>"
        "</div>"
        "<label>Success criteria <span class='hint'>— one per line; at least "
        "one is required before launching</span></label>"
        f"<textarea name='criteria' rows='4'>{esc(criteria)}</textarea>"
        "<label>Constraints <span class='hint'>— one per line, as "
        "<code>TYPE: description</code>, e.g. <code>TIME: must ship in Q3</code>"
        "</span></label>"
        f"<textarea name='constraints' rows='3'>{esc(constraints)}</textarea>"
        "<div class='actions'>"
        f"<button class='primary' type='submit'>"
        f"{'Save changes' if editing else 'Add to backlog'}</button>"
        f"<a class='btn' href='/missions"
        f"{'/' + str(mission.id) if editing else ''}'>Cancel</a>"
        "</div></form>",
        section="backlog",
    )
