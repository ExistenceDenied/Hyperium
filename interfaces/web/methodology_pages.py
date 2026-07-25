"""
Methodology browser.

Read-only. Methodologies are authored as JSON and validated on load; editing
them through a web form would put the platform's most important asset behind
a textarea, with no review and no version history.
"""

from __future__ import annotations

from interfaces.web.layout import esc, page


def catalogue(methodologies, techniques, default: str = "") -> str:
    body = [
        "<h1>Methodologies</h1>",
        "<p class='muted'>A methodology decides what work an engagement "
        "contains. Hyperium automates methodologies; it does not invent "
        "them.</p>",
    ]

    for item in methodologies:
        mark = (
            " <span class='pill ok'>default</span>"
            if item.key == default
            else ""
        )
        body.append(
            "<div class='card'><div class='row'><div>"
            f"<a href='/methodologies/{esc(item.key)}'><strong>"
            f"{esc(item.name)}</strong></a>{mark}"
            f"<div class='muted small'>{esc(item.description)}</div></div>"
            f"<div class='muted small'>{len(item.stages)} stages · "
            f"{len(item.deliverables)} deliverables · "
            f"{len(item.activities)} activities</div>"
            "</div></div>"
        )

    body.append(f"<h2>Techniques <span class='muted'>({len(techniques)})</span></h2>")
    body.append(
        "<p class='muted small'>A capability says what a resource can do; a "
        "technique says how the work is performed.</p>"
    )
    body.append("<table><thead><tr><th>Technique</th><th>Applies to</th>"
                "<th>What it is</th></tr></thead><tbody>")

    for technique in techniques:
        applies = ", ".join(sorted(technique.capabilities)) or "any capability"
        body.append(
            f"<tr><td><strong>{esc(technique.name)}</strong></td>"
            f"<td class='muted small'>{esc(applies)}</td>"
            f"<td class='small'>{esc(technique.description)}</td></tr>"
        )

    body.append("</tbody></table>")

    return page("Methodologies", "".join(body), section="methodologies")


def methodology_detail(methodology, techniques) -> str:
    by_key = {item.key: item for item in techniques}

    body = [
        "<p><a href='/methodologies'>← Methodologies</a></p>",
        f"<h1>{esc(methodology.name)}</h1>",
        f"<p class='muted'>{esc(methodology.key)} · v{esc(methodology.version)}"
        + (f" · {esc(methodology.discipline)}" if methodology.discipline else "")
        + "</p>",
        f"<div class='card'>{esc(methodology.description)}</div>",
    ]

    if methodology.principles:
        entries = "".join(f"<li>{esc(p)}</li>" for p in methodology.principles)
        body.append(f"<h2>Principles</h2><ul>{entries}</ul>")

    body.append("<h2>Stages</h2>")

    for index, stage in enumerate(methodology.stages, start=1):
        after = (
            f" <span class='muted small'>after {esc(', '.join(stage.depends_on))}"
            "</span>"
            if stage.depends_on
            else ""
        )

        body.append(
            f"<div class='card'><h3>{index}. {esc(stage.name)}{after}</h3>"
        )

        if stage.description:
            body.append(f"<p class='muted'>{esc(stage.description)}</p>")

        if stage.quality_gate:
            body.append(_gate(stage.quality_gate))

        for deliverable in stage.deliverables:
            body.append(
                f"<h3>{esc(deliverable.name)} "
                f"<span class='muted small'>{esc(deliverable.key)}</span></h3>"
            )

            if deliverable.sections:
                covers = ", ".join(deliverable.sections)
                body.append(
                    f"<p class='muted small'>Covers: {esc(covers)}</p>"
                )

            body.append("<ul>")
            for activity in deliverable.activities:
                technique = by_key.get(activity.technique or "")
                via = (
                    f" <span class='muted small'>via {esc(technique.name)}</span>"
                    if technique
                    else ""
                )
                needs = ", ".join(activity.capabilities)
                body.append(
                    f"<li>{esc(activity.name)}{via}"
                    f"<br><span class='muted small'>{esc(needs)}</span></li>"
                )
            body.append("</ul>")

        body.append("</div>")

    return page(methodology.name, "".join(body), section="methodologies")


def _gate(gate) -> str:
    checks = []

    if gate.require_approval:
        checks.append("a human approves every deliverable")
    if gate.minimum_words:
        checks.append(f"each is at least {gate.minimum_words} words")
    if gate.required_sections:
        sections = ", ".join(gate.required_sections)
        checks.append(f"each covers {sections}")

    detail = "; ".join(checks) or "no automatic checks"

    return (
        "<p class='small'><span class='pill await'>gate</span> "
        f"The next stage cannot start until {esc(detail)}.</p>"
    )
