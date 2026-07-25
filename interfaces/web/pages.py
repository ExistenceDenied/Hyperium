"""
HTML rendering for the review interface.

These functions read domain objects and return strings. They hold no business
rules — every decision (what is ready, what may be approved) is asked of the
domain, per the adapter rule in 12-interfaces.md.
"""

from __future__ import annotations

from core.execution.deliverable import Deliverable
from core.execution.deliverable_status import DeliverableStatus
from core.execution.execution_result import ExecutionStatus
from core.project.project import Project
from interfaces.web import diff as diffing
from interfaces.web import markdown
from interfaces.web.layout import error_page, esc, page  # noqa: F401

_STATUS_CLASS = {
    DeliverableStatus.AWAITING_APPROVAL: "await",
    DeliverableStatus.APPROVED: "ok",
    DeliverableStatus.CHANGES_REQUESTED: "bad",
    DeliverableStatus.DRAFT: "draft",
}


def pill(deliverable: Deliverable) -> str:
    css = _STATUS_CLASS.get(deliverable.status, "draft")

    return (
        f"<span class='pill {css}'>"
        f"{esc(deliverable.status.value.replace('_', ' '))}</span>"
    )


def index(
    engagements: list[Project],
    missions: list,
    unreadable: list[tuple] | None = None,
) -> str:
    waiting = sum(len(p.awaiting_approval) for p in engagements)

    body = ["<h1>Engagements</h1>"]

    if waiting:
        body.append(
            f"<div class='banner'><strong>{waiting} deliverable(s)"
            "</strong> are waiting for your review.</div>"
        )

    for project_id, reason in unreadable or []:
        body.append(
            "<div class='banner'><strong>Could not read engagement "
            f"{esc(project_id)}.</strong><br>"
            f"<span class='muted'>{esc(reason)}</span></div>"
        )

    if not engagements:
        body.append(
            "<p class='muted'>No engagements yet. Launch one with "
            "<code>python main.py run \"Title\" \"Objective\"</code>.</p>"
        )

    for project in engagements:
        result = project.execution_result
        status = result.status.value if result else "—"
        pending = len(project.awaiting_approval)
        note = (
            f"<span class='pill await'>{pending} awaiting review</span>"
            if pending
            else ""
        )

        body.append(
            "<div class='card'><div class='row'>"
            f"<div><a href='/engagement/{project.id}'>"
            f"<strong>{esc(project.mission.title)}</strong></a>"
            f"<div class='muted'>{esc(project.mission.objective.description)}</div>"
            "</div>"
            f"<div>{note} <span class='pill'>{esc(status)}</span></div>"
            "</div></div>"
        )

    body.append("<h2>Mission backlog</h2>")

    if not missions:
        body.append("<p class='muted'>The backlog is empty.</p>")
    else:
        body.append(
            "<table><thead><tr><th>Priority</th><th>Status</th>"
            "<th>Mission</th></tr></thead><tbody>"
        )
        for mission in missions:
            body.append(
                f"<tr><td>{esc(mission.priority.name)}</td>"
                f"<td>{esc(mission.status.value)}</td>"
                f"<td>{esc(mission.title)}</td></tr>"
            )
        body.append("</tbody></table>")
        body.append(
            "<p class='muted'>Missions are managed from the command line: "
            "<code>python main.py mission --help</code>.</p>"
        )

    return page("Engagements", "".join(body), section="engagements")


def engagement(project: Project, busy: bool = False, error: str = "") -> str:
    result = project.execution_result
    status = result.status if result else None

    body = [
        f"<p><a href='/missions/{project.mission.id}'>&larr; Mission</a></p>",
        f"<h1>{esc(project.mission.title)}</h1>",
        f"<p class='muted'>{esc(project.mission.objective.description)}</p>",
        f"<p><span class='pill'>{esc(status.value if status else '—')}</span> "
        f"<span class='muted'>{esc(project.id)}</span></p>",
    ]

    if error:
        body.append(f"<div class='banner'><strong>Failed:</strong> {esc(error)}</div>")

    if busy:
        body.append(
            "<div class='banner'>Working… Hyperium is generating content. "
            "This page refreshes automatically.</div>"
        )

    plan = project.execution_plan

    if plan is not None and plan.methodology_key:
        body.append(
            f"<p class='muted'>Methodology: "
            f"<strong>{esc(plan.methodology_key)}</strong></p>"
        )

    current_stage = object()

    for deliverable in project.deliverables:
        if deliverable.stage != current_stage:
            current_stage = deliverable.stage
            body.append(_stage_heading(plan, current_stage))

        version = deliverable.latest_version()
        activities = deliverable.activities
        done = sum(1 for a in activities if a.is_completed)

        body.append("<div class='card'>")
        body.append(
            "<div class='row'><div>"
            f"<strong>{esc(deliverable.name)}</strong> "
            f"<span class='muted'>{esc(deliverable.key)}</span>"
            f"<div class='muted'>{done}/{len(activities)} activities complete"
            + (f" · v{version.version}" if version else " · no content yet")
            + "</div></div>"
            f"<div>{pill(deliverable)}</div></div>"
        )

        if version:
            body.append(
                "<div class='actions'>"
                f"<a class='btn' href='/engagement/{project.id}"
                f"/deliverable/{esc(deliverable.key)}'>Read</a>"
            )
            if len(deliverable.versions) > 1:
                body.append(
                    f"<a class='btn' href='/engagement/{project.id}"
                    f"/deliverable/{esc(deliverable.key)}/diff'>"
                    f"Compare v{len(deliverable.versions) - 1} → "
                    f"v{len(deliverable.versions)}</a>"
                )
            body.append("</div>")

        if deliverable.status is DeliverableStatus.AWAITING_APPROVAL:
            body.append(_review_form(project, deliverable))

        body.append(_submission_forms(project, deliverable))
        body.append("</div>")

    if status is ExecutionStatus.AWAITING_APPROVAL and not busy:
        body.append(
            "<p class='muted'>Approve a deliverable above to unblock the work "
            "that depends on it.</p>"
        )

    if not busy and status in (
        ExecutionStatus.AWAITING_APPROVAL,
        ExecutionStatus.BLOCKED,
    ):
        body.append(
            f"<form method='post' action='/engagement/{project.id}/resume'>"
            "<button class='primary' type='submit'>Continue the engagement"
            "</button> <span class='muted'>Runs the next activities; may take "
            "a few minutes.</span></form>"
        )

    if result and result.messages:
        body.append("<h2>Activity log</h2><div class='card'>")
        body.extend(f"<div class='muted'>{esc(m)}</div>" for m in result.messages)
        body.append("</div>")

    return page(
        project.mission.title,
        "".join(body),
        refresh=busy,
        section="engagements",
    )


def _stage_heading(plan, stage_key: str | None) -> str:
    """
    A stage heading with its gate status.

    The failures matter more than the badge: a stalled engagement should say
    what is holding it, not merely that something is.
    """
    if not stage_key or plan is None:
        return ""

    gate = plan.gate_result(stage_key)
    name = stage_key

    stage = plan.stage(stage_key)

    if stage is not None and stage.name:
        name = stage.name

    badge = (
        "<span class='pill ok'>gate passed</span>"
        if gate.passed
        else "<span class='pill await'>gate not met</span>"
    )

    heading = f"<h2>{esc(name)} {badge}</h2>"

    if not gate.passed and gate.failures:
        items = "".join(f"<li>{esc(failure)}</li>" for failure in gate.failures)
        heading += f"<ul class='muted'>{items}</ul>"

    return heading


def _submission_forms(project: Project, deliverable: Deliverable) -> str:
    """
    Activities allocated to a person are done outside Hyperium; this is where
    the result comes back in. The plan decides which are ready — the page only
    asks it.
    """
    plan = project.execution_plan

    if plan is None:
        return ""

    forms = []

    for activity in deliverable.activities:
        if activity.is_completed:
            continue

        resource = plan.get_resource(activity)

        if resource is None or type(resource).__name__ == "AIResource":
            continue

        if not plan.is_ready(activity):
            continue

        forms.append(
            f"<form method='post' action='/engagement/{project.id}"
            f"/activity/{esc(activity.key)}/submit' style='margin-top:14px'>"
            f"<label>{esc(activity.name)} "
            f"<span class='hint'>— assigned to {esc(resource.name)}</span>"
            "</label>"
            "<textarea name='content' rows='5' required placeholder='Paste "
            "the work you completed for this activity.'></textarea>"
            "<div class='actions'><button class='primary' type='submit'>"
            "Submit work</button></div></form>"
        )

    return "".join(forms)


def _review_form(project: Project, deliverable: Deliverable) -> str:
    action = f"/engagement/{project.id}/deliverable/{esc(deliverable.key)}"

    return (
        f"<form method='post' action='{action}/review' style='margin-top:14px'>"
        "<textarea name='note' rows='3' placeholder='Feedback — required when "
        "sending back for rework.'></textarea>"
        "<div class='actions'>"
        "<button class='primary' name='decision' value='approve' type='submit'>"
        "Approve</button>"
        "<button class='danger' name='decision' value='reject' type='submit'>"
        "Request changes</button>"
        "</div></form>"
    )


def deliverable_view(
    project: Project,
    deliverable: Deliverable,
    version_number: int | None = None,
) -> str:
    versions = deliverable.versions

    if not versions:
        return page(
            deliverable.name,
            f"<h1>{esc(deliverable.name)}</h1>"
            "<p class='muted'>No content has been produced yet.</p>",
        )

    selected = versions[-1]

    if version_number is not None:
        matches = [v for v in versions if v.version == version_number]
        if not matches:
            raise KeyError(f"No version {version_number} of '{deliverable.key}'.")
        selected = matches[0]

    body = [
        f"<p><a href='/engagement/{project.id}'>← "
        f"{esc(project.mission.title)}</a></p>",
        f"<h1>{esc(deliverable.name)}</h1>",
        f"<p>{pill(deliverable)} <span class='muted'>v{selected.version} of "
        f"{len(versions)} · {esc(selected.filename)} · by "
        f"{esc(selected.created_by or 'unknown')}</span></p>",
    ]

    base = f"/engagement/{project.id}/deliverable/{esc(deliverable.key)}"
    body.append(
        f"<div class='actions'><a class='btn' href='{base}/raw"
        f"?version={selected.version}'>Download {esc(selected.filename)}</a>"
        "</div>"
    )

    if len(versions) > 1:
        links = " ".join(
            f"<a class='btn' href='/engagement/{project.id}/deliverable/"
            f"{esc(deliverable.key)}?version={v.version}'>v{v.version}</a>"
            for v in versions
        )
        body.append(
            f"<div class='actions'>{links}"
            f"<a class='btn' href='/engagement/{project.id}/deliverable/"
            f"{esc(deliverable.key)}/diff'>Compare</a></div>"
        )

    if selected.review_summary:
        body.append(
            "<div class='banner'><strong>Reviewer feedback on this version:"
            f"</strong><br>{esc(selected.review_summary)}</div>"
        )

    if deliverable.status is DeliverableStatus.AWAITING_APPROVAL:
        body.append(_review_form(project, deliverable))

    body.append(f"<div class='card doc'>{markdown.render(selected.content)}</div>")

    return page(deliverable.name, "".join(body))


def diff_view(
    project: Project,
    deliverable: Deliverable,
    before_number: int,
    after_number: int,
) -> str:
    by_number = {v.version: v for v in deliverable.versions}

    if before_number not in by_number or after_number not in by_number:
        raise KeyError("Unknown version for comparison.")

    before, after = by_number[before_number], by_number[after_number]
    added, removed = diffing.summary(before, after)

    body = [
        f"<p><a href='/engagement/{project.id}'>← "
        f"{esc(project.mission.title)}</a></p>",
        f"<h1>{esc(deliverable.name)}</h1>",
        f"<p class='muted'>v{before.version} → v{after.version} · "
        f"<span style='color:var(--ok)'>+{added}</span> "
        f"<span style='color:var(--bad)'>−{removed}</span> lines</p>",
    ]

    if before.review_summary:
        body.append(
            "<div class='banner'><strong>Why it was sent back:</strong><br>"
            f"{esc(before.review_summary)}</div>"
        )

    options = " ".join(
        f"<a class='btn' href='/engagement/{project.id}/deliverable/"
        f"{esc(deliverable.key)}/diff?from={v}&to={after.version}'>"
        f"v{v} → v{after.version}</a>"
        for v in sorted(by_number)
        if v != after.version
    )

    if len(by_number) > 2:
        body.append(f"<div class='actions'>{options}</div>")

    body.append(diffing.unified(before, after))

    return page(f"{deliverable.name} diff", "".join(body))
