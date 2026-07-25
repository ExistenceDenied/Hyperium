"""
HTML rendering for the review interface.

These functions read domain objects and return strings. They hold no business
rules — every decision (what is ready, what may be approved) is asked of the
domain, per the adapter rule in 12-interfaces.md.
"""

from __future__ import annotations

import html

from core.execution.deliverable import Deliverable
from core.execution.deliverable_status import DeliverableStatus
from core.execution.execution_result import ExecutionStatus
from core.project.project import Project
from interfaces.web import diff as diffing
from interfaces.web import markdown

STYLE = """
:root {
  --bg:#f7f8fa; --fg:#14171f; --muted:#61697a; --line:#e0e4ea; --card:#fff;
  --accent:#2f6feb; --ok:#1a7f47; --warn:#a8630a; --bad:#b4232c;
  --add-bg:#e5f5ea; --del-bg:#fdeaec;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg:#12141a; --fg:#e6e9f0; --muted:#98a1b3; --line:#272b36; --card:#191c24;
    --accent:#6b9bff; --ok:#4cc38a; --warn:#e0a458; --bad:#f0707a;
    --add-bg:#14301f; --del-bg:#3a1a1e;
  }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.6
  ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }
a { color:var(--accent); }
.wrap { max-width:980px; margin:0 auto; padding:24px 20px 72px; }
header.top { border-bottom:1px solid var(--line); background:var(--card); }
header.top .wrap { padding:14px 20px; display:flex; gap:16px; align-items:baseline; }
header.top strong { font-size:17px; }
h1 { font-size:24px; margin:22px 0 6px; }
h2 { font-size:19px; margin:26px 0 8px; }
.muted { color:var(--muted); }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:16px 18px; margin:12px 0; }
.row { display:flex; justify-content:space-between; gap:16px; align-items:center;
  flex-wrap:wrap; }
.pill { display:inline-block; padding:2px 9px; border-radius:999px; font-size:12px;
  font-weight:600; border:1px solid var(--line); white-space:nowrap; }
.pill.await { color:var(--warn); border-color:var(--warn); }
.pill.ok { color:var(--ok); border-color:var(--ok); }
.pill.bad { color:var(--bad); border-color:var(--bad); }
.pill.draft { color:var(--muted); }
table { border-collapse:collapse; width:100%; margin:12px 0; }
th,td { border:1px solid var(--line); padding:7px 10px; text-align:left;
  vertical-align:top; }
th { background:rgba(127,127,127,.08); }
pre { background:rgba(127,127,127,.10); padding:12px; border-radius:8px;
  overflow-x:auto; }
code { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:13px; }
blockquote { border-left:3px solid var(--line); margin:8px 0; padding:2px 12px;
  color:var(--muted); }
button, .btn { font:inherit; padding:7px 14px; border-radius:8px; cursor:pointer;
  border:1px solid var(--line); background:var(--card); color:var(--fg);
  text-decoration:none; display:inline-block; }
button.primary { background:var(--accent); border-color:var(--accent); color:#fff; }
button.danger { color:var(--bad); border-color:var(--bad); }
textarea { width:100%; font:inherit; padding:9px; border-radius:8px;
  border:1px solid var(--line); background:var(--bg); color:var(--fg); }
.doc { overflow-wrap:anywhere; }
.doc table { display:block; overflow-x:auto; }
.diff { font-family:ui-monospace,SFMono-Regular,Consolas,monospace; font-size:12.5px;
  border:1px solid var(--line); border-radius:8px; overflow-x:auto; }
.diff-line { padding:1px 10px; white-space:pre; }
.diff-line.add { background:var(--add-bg); }
.diff-line.del { background:var(--del-bg); }
.diff-line.hunk { background:rgba(127,127,127,.14); color:var(--muted); }
.diff-line.meta { color:var(--muted); }
.banner { border-left:4px solid var(--warn); padding:10px 14px; margin:14px 0;
  background:var(--card); border-radius:0 8px 8px 0; }
.actions { display:flex; gap:10px; flex-wrap:wrap; margin-top:12px; }
"""

_STATUS_CLASS = {
    DeliverableStatus.AWAITING_APPROVAL: "await",
    DeliverableStatus.APPROVED: "ok",
    DeliverableStatus.CHANGES_REQUESTED: "bad",
    DeliverableStatus.DRAFT: "draft",
}


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def page(title: str, body: str, refresh: bool = False) -> str:
    meta = '<meta http-equiv="refresh" content="4">' if refresh else ""

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"{meta}<title>{esc(title)} · Hyperium</title><style>{STYLE}</style>"
        "</head><body><header class='top'><div class='wrap'>"
        "<strong><a href='/' style='text-decoration:none;color:inherit'>"
        "Hyperium</a></strong>"
        "<span class='muted'>review</span></div></header>"
        f"<div class='wrap'>{body}</div></body></html>"
    )


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

    return page("Engagements", "".join(body))


def engagement(project: Project, busy: bool = False, error: str = "") -> str:
    result = project.execution_result
    status = result.status if result else None

    body = [
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

    if plan is not None and plan.methodology is not None:
        body.append(
            f"<p class='muted'>Methodology: "
            f"<strong>{esc(plan.methodology.name)}</strong> "
            f"({esc(plan.methodology.key)})</p>"
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

    return page(project.mission.title, "".join(body), refresh=busy)


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

    if plan.methodology is not None:
        try:
            name = plan.methodology.stage(stage_key).name
        except KeyError:
            pass

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


def error_page(message: str, code: int = 404) -> str:
    return page(
        "Not found" if code == 404 else "Error",
        f"<h1>{code}</h1><p class='muted'>{esc(message)}</p>"
        "<p><a href='/'>Back to engagements</a></p>",
    )
