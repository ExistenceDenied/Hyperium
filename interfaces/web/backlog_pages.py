"""
Mission backlog views.

Every decision here is asked of `MissionBacklogService` — whether a mission is
complete, whether it may be edited, what may be deleted. These functions only
choose what to show.
"""

from __future__ import annotations

from core.execution.deliverable_status import DeliverableStatus
from core.missions.mission_priority import MissionPriority
from core.missions.mission_status import MissionStatus
from interfaces.web.layout import esc, page

_STATUS_CLASS = {
    MissionStatus.DRAFT: "draft",
    MissionStatus.READY: "ok",
    MissionStatus.LAUNCHED: "await",
    MissionStatus.ARCHIVED: "draft",
}

_DELIVERABLE_CLASS = {
    DeliverableStatus.AWAITING_APPROVAL: "await",
    DeliverableStatus.APPROVED: "ok",
    DeliverableStatus.CHANGES_REQUESTED: "bad",
    DeliverableStatus.DRAFT: "draft",
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

        if mission.id in launching:
            action = "<span class='muted small'>launching…</span>"
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
        f"<p class='small'><a href='/missions?all="
        f"{'0' if show_archived else '1'}'>"
        f"{'Hide' if show_archived else 'Show'} archived</a></p>"
    )

    return page(
        "Backlog", "".join(body), refresh=bool(launching), section="backlog"
    )


def mission_detail(
    mission,
    methodologies,
    project=None,
    launching: bool = False,
    error: str = "",
    project_error: str = "",
) -> str:
    body = [
        "<p><a href='/missions'>← Backlog</a></p>",
        f"<h1>{esc(mission.title)}</h1>",
        f"<p>{status_pill(mission)} "
        f"<span class='pill'>{esc(mission.priority.name)}</span> "
        + (
            f"<span class='pill'>{esc(mission.methodology)}</span> "
            if mission.methodology
            else ""
        )
        + f"<span class='muted small'>{esc(mission.id)}</span></p>",
        f"<div class='card'><p>{esc(mission.objective.description)}</p></div>",
    ]

    if error:
        body.append(
            "<div class='banner bad'><strong>Could not launch.</strong><br>"
            f"{esc(error)}</div>"
        )

    if launching:
        body.append(
            "<div class='banner'>Launching… Hyperium is planning and running "
            "the first stage. This page refreshes automatically.</div>"
        )

    body.append(_facts(mission))

    if mission.is_launched:
        body.append(_engagement_summary(mission, project, project_error))
    elif not launching:
        body.append(_launch_form(mission, methodologies))

    if not launching:
        body.append(_manage(mission))

    return page(
        mission.title, "".join(body), refresh=launching, section="backlog"
    )


def _engagement_summary(mission, project, project_error: str) -> str:
    """
    The deliverables, shown on the mission itself.

    A mission is what someone thinks in terms of; making them navigate to a
    separate engagement to find out what it produced is the wrong shape.
    """
    if project_error:
        return (
            "<div class='banner bad'><strong>The engagement could not be "
            f"read.</strong><br>{esc(project_error)}</div>"
        )

    if project is None:
        return (
            f"<p class='muted'>Launched as engagement "
            f"<code>{esc(mission.project_id)}</code>.</p>"
        )

    result = project.execution_result
    plan = project.execution_plan
    status = result.status.value if result else "—"

    blocks = [
        "<h2>Deliverables</h2>",
        f"<p><span class='pill'>{esc(status)}</span> "
        f"<a class='small' href='/engagement/{project.id}'>"
        "Open the full engagement →</a></p>",
    ]

    if not project.deliverables:
        blocks.append("<p class='muted'>Nothing produced yet.</p>")
        return "".join(blocks)

    current = object()

    for deliverable in project.deliverables:
        if deliverable.stage != current:
            current = deliverable.stage
            blocks.append(_stage_line(plan, current))

        version = deliverable.latest_version()
        css = _DELIVERABLE_CLASS.get(deliverable.status, "draft")
        pill = (
            f"<span class='pill {css}'>"
            f"{esc(deliverable.status.value.replace('_', ' '))}</span>"
        )

        if version is None:
            detail = "<span class='muted small'>not produced yet</span>"
            links = ""
        else:
            detail = (
                f"<span class='muted small'>v{version.version} · "
                f"{esc(version.filename)}</span>"
            )
            base = f"/engagement/{project.id}/deliverable/{esc(deliverable.key)}"
            links = (
                f"<div class='actions'><a class='btn' href='{base}'>Read</a>"
                f"<a class='btn' href='{base}/raw'>Download</a>"
                + (
                    f"<a class='btn' href='{base}/diff'>Compare versions</a>"
                    if len(deliverable.versions) > 1
                    else ""
                )
                + "</div>"
            )

        blocks.append(
            "<div class='card'><div class='row'><div>"
            f"<strong>{esc(deliverable.name)}</strong><br>{detail}</div>"
            f"<div>{pill}</div></div>{links}</div>"
        )

    return "".join(blocks)


def _stage_line(plan, stage_key) -> str:
    if not stage_key or plan is None:
        return ""

    gate = plan.gate_result(stage_key)
    stage = plan.stage(stage_key)
    name = stage.name if stage and stage.name else stage_key

    badge = (
        "<span class='pill ok'>gate passed</span>"
        if gate.passed
        else "<span class='pill await'>gate not met</span>"
    )

    heading = f"<h3>{esc(name)} {badge}</h3>"

    if not gate.passed and gate.failures:
        items = "".join(f"<li>{esc(f)}</li>" for f in gate.failures)
        heading += f"<ul class='muted small'>{items}</ul>"

    return heading


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
            "cannot be launched yet. Edit it to add one.</div>"
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
        "</button></div></form>"
    )


def _manage(mission) -> str:
    actions = []

    if mission.is_editable:
        actions.append(
            f"<a class='btn' href='/missions/{mission.id}/edit'>Edit</a>"
        )

    if mission.status is MissionStatus.DRAFT and mission.is_complete:
        actions.append(
            f"<form method='post' action='/missions/{mission.id}/ready'>"
            "<button type='submit'>Mark ready</button></form>"
        )

    if mission.status is MissionStatus.ARCHIVED:
        actions.append(
            f"<form method='post' action='/missions/{mission.id}/restore'>"
            "<button type='submit'>Restore</button></form>"
        )
    elif not mission.is_launched:
        actions.append(
            f"<form method='post' action='/missions/{mission.id}/archive'>"
            "<button type='submit'>Archive</button></form>"
        )

    actions.append(
        f"<a class='btn danger' href='/missions/{mission.id}/delete'>Delete</a>"
    )

    note = (
        "<p class='muted small'>A launched mission is frozen: the engagement "
        "holds its own copy, and editing this would let the two drift "
        "apart.</p>"
        if mission.is_launched
        else ""
    )

    return f"<h2>Manage</h2><div class='actions'>{''.join(actions)}</div>{note}"


def confirm_delete(mission) -> str:
    """
    Deleting is irreversible, and there is no scripting on these pages, so the
    confirmation is a page rather than a dialog.
    """
    warning = (
        "<div class='banner bad'>This mission has been launched as engagement "
        f"<code>{esc(mission.project_id)}</code>. Deleting it orphans that "
        "engagement — the work stays on disk but nothing points at it.</div>"
        if mission.is_launched
        else ""
    )

    return page(
        "Delete mission",
        f"<p><a href='/missions/{mission.id}'>← {esc(mission.title)}</a></p>"
        f"<h1>Delete “{esc(mission.title)}”?</h1>{warning}"
        "<p class='muted'>This cannot be undone. Archiving keeps the mission "
        "and hides it from the backlog.</p>"
        f"<form method='post' action='/missions/{mission.id}/delete'>"
        "<div class='actions'>"
        "<button class='danger' type='submit'>Delete permanently</button>"
        f"<a class='btn' href='/missions/{mission.id}'>Cancel</a>"
        "</div></form>",
        section="backlog",
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
        return values.get(name, fallback)

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
    stakeholders = value(
        "stakeholders",
        "\n".join(f"{s.name}: {s.role}" for s in mission.stakeholders)
        if editing
        else "",
    )
    chosen = value("methodology", mission.methodology if editing else "")
    priority = value("priority", mission.priority.name if editing else "MEDIUM")

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

    banner = f"<div class='banner bad'>{esc(error)}</div>" if error else ""

    return page(
        "Edit mission" if editing else "New mission",
        f"<p><a href='/missions"
        f"{'/' + str(mission.id) if editing else ''}'>← Back</a></p>"
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
        "<label>Stakeholders <span class='hint'>— one per line, as "
        "<code>Name: role</code></span></label>"
        f"<textarea name='stakeholders' rows='3'>{esc(stakeholders)}</textarea>"
        "<div class='actions'>"
        "<button class='primary' type='submit'>"
        f"{'Save changes' if editing else 'Add to backlog'}</button>"
        f"<a class='btn' href='/missions"
        f"{'/' + str(mission.id) if editing else ''}'>Cancel</a>"
        "</div></form>",
        section="backlog",
    )
