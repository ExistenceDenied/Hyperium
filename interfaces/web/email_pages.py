"""The Email page: watch an Outlook folder and draft replies for you to send."""

from __future__ import annotations

from interfaces.web.layout import esc, page

_CATEGORY_PILL = {
    "reply": "ok",
    "escalate": "bad",
    "fyi": "draft",
    "skip": "draft",
    "task": "await",
}


def _handled(items) -> str:
    if not items:
        return "<p class='muted small'>Nothing triaged yet.</p>"

    def when(item):
        return esc((item.get("at", "") or "")[:16].replace("T", " "))

    def cell(item):
        category = item.get("category") or "—"
        kind = _CATEGORY_PILL.get(category, "draft")
        actions = "; ".join(item.get("actions", [])) or item.get("summary", "")
        return (
            f"<span class='pill {kind}'>{esc(category)}</span> "
            f"<span class='small muted'>{esc(actions[:80])}</span>"
        )

    rows = "".join(
        f"<tr><td>{esc(item.get('sender', ''))}</td>"
        f"<td>{esc(item.get('subject', ''))}</td>"
        f"<td>{cell(item)}</td>"
        f"<td class='small muted'>{when(item)}</td></tr>"
        for item in items
    )
    return (
        "<table><thead><tr><th>From</th><th>Subject</th>"
        "<th>Triage &amp; action</th><th style='width:130px'>When</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def email_page(enabled: bool, folder: str, connected: bool, handled) -> str:
    on = "checked" if enabled else ""
    warn = (
        ""
        if connected
        else (
            "<div class='banner'>Connect <strong>Outlook / Microsoft 365</strong> "
            "on the <a href='/connections'>Connect</a> page first — the worker "
            "reads and drafts through it.</div>"
        )
    )

    body = (
        "<h1>Email</h1>"
        "<p class='muted'>Point the worker at one Outlook folder. On a schedule "
        "it triages each new message — drafting a reply only when one is needed, "
        "flagging what needs you, and turning work the mail implies into tasks. "
        "Replies are left as <strong>drafts</strong> in your mailbox, using your "
        "business memory; it never sends — you review and send each one.</p>"
        + warn
        + "<form method='post' action='/email'>"
        "<label style='display:flex;gap:8px;font-weight:600'>"
        f"<input type='checkbox' name='enabled' value='1' style='width:auto' {on}> "
        "Draft replies for new mail in this folder</label>"
        "<label>Folder"
        f"<input name='folder' value='{esc(folder)}' placeholder='Inbox'></label>"
        "<p class='muted small'>Tip: route the mail you want handled into a "
        "dedicated folder (e.g. a rule that files it under 'Hyperium'), so the "
        "worker only ever sees what you intend.</p>"
        "<div class='actions'><button class='primary' type='submit'>Save</button>"
        "</div></form>"
        "<h2>Triage log</h2>" + _handled(handled)
    )
    return page("Email", body, section="email")
