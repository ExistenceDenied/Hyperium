"""The alert feed: everything the system wanted you to know, newest first."""

from __future__ import annotations

from interfaces.web.layout import esc, page

_KIND_PILL = {"approval": "bad", "error": "bad", "task": "ok"}


def notifications_index(notes) -> str:
    if notes:
        rows = []
        for note in notes:
            kind = _KIND_PILL.get(note.kind, "draft")
            dot = "" if note.read else "● "
            when = note.at.strftime("%Y-%m-%d %H:%M")
            text = esc(note.text)
            body = f"<a href='{esc(note.link)}'>{text}</a>" if note.link else text
            rows.append(
                f"<tr><td><span class='pill {kind}'>{esc(note.kind)}</span></td>"
                f"<td>{dot}{body}</td>"
                f"<td class='small muted'>{when}</td></tr>"
            )
        listing = (
            "<table><thead><tr><th style='width:110px'>Kind</th>"
            "<th>Alert</th><th style='width:140px'>When</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )
        clear = (
            "<form method='post' action='/notifications/read' style='margin:0'>"
            "<button type='submit'>Mark all read</button></form>"
        )
    else:
        listing = "<div class='empty'>No alerts yet.</div>"
        clear = ""

    body = "<div class='row'><h1>Alerts</h1>" + clear + "</div>" + listing
    return page("Alerts", body, section="notifications")
