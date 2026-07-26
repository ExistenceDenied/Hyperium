"""
Manage the technique library: create, edit, delete, and each technique's
downloadable/uploadable template.

A capability says what a resource can do; a technique says how the work is
performed. Its template is the shape its output follows.
"""

from __future__ import annotations

from core.capabilities.capability_catalog import CapabilityCatalog
from interfaces.web.layout import esc, page


def techniques_index(techniques) -> str:
    new = "<a class='btn primary' href='/techniques/new'>New technique</a>"

    rows = []
    for technique in techniques:
        applies = ", ".join(sorted(technique.capabilities)) or "any capability"
        badge = (
            " <span class='pill ok'>template</span>" if technique.template else ""
        )
        rows.append(
            f"<tr><td><a href='/techniques/{esc(technique.key)}'>"
            f"{esc(technique.name)}</a>{badge}</td>"
            f"<td class='muted small'>{esc(applies)}</td>"
            f"<td class='small'>{esc(technique.description)}</td></tr>"
        )

    body = (
        "<div class='row'><h1>Techniques</h1>" + new + "</div>"
        "<p class='muted'>A technique says how work is performed, and can carry "
        "a template its output follows.</p>"
        "<table><thead><tr><th>Technique</th><th>Applies to</th>"
        "<th>What it is</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )

    return page("Techniques", body, section="techniques")


def technique_form(technique=None) -> str:
    editing = technique is not None
    key = esc(technique.key) if editing else ""
    selected = technique.capabilities if editing else frozenset()

    key_field = (
        f"<input name='key' value='{key}' readonly>"
        if editing
        else "<input name='key' required placeholder='e.g. swot-analysis'>"
    )

    capabilities = "".join(
        "<label style='display:flex;gap:8px;font-weight:400;margin:4px 0'>"
        f"<input type='checkbox' name='capabilities' value='{cap}' "
        "style='width:auto'"
        + (" checked" if cap in selected else "")
        + f"> {esc(CapabilityCatalog.get(cap).name)}</label>"
        for cap in CapabilityCatalog.keys()
    )

    parts = [
        "<p><a href='/techniques'>← Techniques</a></p>",
        f"<h1>{'Edit technique' if editing else 'New technique'}</h1>",
        f"<form method='post' action='/techniques{'/' + key if editing else ''}'>",
        f"<label>Key{key_field}</label>",
        "<label>Name<input name='name' value='"
        + (esc(technique.name) if editing else "")
        + "' required></label>",
        "<label>Description<textarea name='description' rows='2'>"
        + (esc(technique.description) if editing else "")
        + "</textarea></label>",
        "<label>Guidance<textarea name='guidance' rows='6'>"
        + (esc(technique.guidance) if editing else "")
        + "</textarea></label>",
        f"<label>Applies to</label><div class='card'>{capabilities}</div>",
        "<div class='actions'><button class='primary' type='submit'>Save</button>"
        "<a class='btn' href='/techniques'>Cancel</a></div></form>",
    ]

    if editing:
        download = (
            f"<a class='btn' href='/techniques/{key}/template'>Download template</a>"
            if technique.template
            else "<span class='muted small'>No template yet.</span>"
        )
        parts.append(
            "<h3>Template</h3>"
            "<p class='muted small'>A Markdown template the technique's output "
            "follows; the agent uses it when performing the technique.</p>"
            f"<p>{download}</p>"
            f"<form method='post' action='/techniques/{key}/template' "
            "enctype='multipart/form-data'>"
            "<input type='file' name='files' accept='.md,.txt'>"
            "<div class='actions'><button type='submit'>Upload template</button>"
            "</div></form>"
            f"<form method='post' action='/techniques/{key}/delete' "
            "style='margin-top:16px'>"
            "<button class='danger' type='submit'>Delete technique</button></form>"
        )

    return page("Technique", "".join(parts), section="techniques")
