"""
The Rules page: a small decision table that governs the agent, deterministically.

Business rules live here as data, not code. Triage decides what an email is; a
rule decides what to do about it — draft or send, and whether to attach what the
agent produced. Rules are evaluated in order, top to bottom, first match wins per
outcome, so a specific rule above a general one overrides it.
"""

from __future__ import annotations

from interfaces.web.layout import esc, page

_INPUTS = ("sender", "subject", "category", "priority", "confidence")
_OPS = (
    "startsWith", "equals", "notEquals", "contains", "in", "matches",
    "gte", "lte", "any",
)


def _options(values, selected=""):
    return "".join(
        f"<option value='{esc(v)}'{' selected' if v == selected else ''}>{esc(v)}"
        "</option>"
        for v in values
    )


def _rule_row(rule) -> str:
    if rule.conditions:
        when = " and ".join(
            f"<code>{esc(c.input)} {esc(c.op)} {esc(c.value)}</code>"
            for c in rule.conditions
        )
    else:
        when = "<code>always</code>"
    then = ", ".join(
        f"{esc(k)} = <strong>{esc(v)}</strong>" for k, v in rule.outputs.items()
    )
    state = "on" if rule.enabled else "off"
    kind = "ok" if rule.enabled else "draft"
    return (
        f"<tr><td><span class='pill {kind}'>{state}</span></td>"
        f"<td>{esc(rule.name)}</td><td class='small'>{when}</td>"
        f"<td class='small'>{then}</td>"
        "<td style='white-space:nowrap'>"
        f"<form method='post' action='/rules/{rule.id}/toggle' "
        "style='display:inline;margin:0'><button type='submit'>"
        f"{'Pause' if rule.enabled else 'Enable'}</button></form> "
        f"<form method='post' action='/rules/{rule.id}/delete' "
        "style='display:inline;margin:0'>"
        "<button class='danger' type='submit'>Delete</button></form></td></tr>"
    )


def rules_index(rules, sending_enabled: bool) -> str:
    rules = list(rules)
    switch = (
        "<div class='card'><div class='row'><div>"
        "<strong>Outbound sending</strong><div class='small muted'>"
        "Master switch. While off, every reply is a draft no matter what a rule "
        "says. A rule can only ever send a reply back to the original sender."
        "</div></div>"
        f"<form method='post' action='/rules/sending' style='margin:0'>"
        f"<button class='{'danger' if sending_enabled else 'primary'}' "
        f"type='submit'>{'Turn sending OFF' if sending_enabled else 'Turn sending ON'}"
        "</button></form></div>"
        f"<p class='small'>Currently: <span class='pill "
        f"{'bad' if sending_enabled else 'draft'}'>"
        f"{'ON — rules may send' if sending_enabled else 'OFF — drafts only'}"
        "</span></p></div>"
    )

    if rules:
        rows = "".join(_rule_row(r) for r in rules)
        table = (
            "<table><thead><tr><th style='width:60px'>State</th><th>Rule</th>"
            "<th>When</th><th>Then</th><th style='width:150px'></th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
    else:
        table = "<div class='empty'>No rules yet. Add one below.</div>"

    form = (
        "<h2>New rule</h2>"
        "<form method='post' action='/rules'>"
        "<label>Name<input name='name' required placeholder='e.g. Reply to myself "
        "is sent'></label>"
        "<p class='small muted' style='margin:10px 0 2px'>When this condition "
        "holds (leave the operator as <code>any</code> for a catch-all):</p>"
        "<div class='grid2'>"
        f"<label>Input<select name='input'>{_options(_INPUTS)}</select></label>"
        f"<label>Operator<select name='op'>{_options(_OPS)}</select></label>"
        "</div>"
        "<label>Value <span class='hint'>(comma-separated = any of)</span>"
        "<input name='value' placeholder='kris.leunis, krisleunis'></label>"
        "<p class='small muted' style='margin:10px 0 2px'>Then apply:</p>"
        "<div class='grid2'>"
        "<label>Triage as<select name='category'>"
        "<option value=''>— leave to the model —</option>"
        "<option value='reply'>reply</option>"
        "<option value='escalate'>escalate</option>"
        "<option value='fyi'>fyi</option>"
        "<option value='skip'>skip</option>"
        "</select></label>"
        "<label>Delivery<select name='delivery'>"
        "<option value=''>— leave to default —</option>"
        "<option value='draft'>draft (never send)</option>"
        "<option value='send'>send (gated by the switch)</option>"
        "</select></label>"
        "</div>"
        "<label style='display:flex;gap:8px;align-items:center'>"
        "<input type='checkbox' name='attach_deliverables' value='true' "
        "style='width:auto'> Attach deliverables</label>"
        "<div class='actions'><button class='primary' type='submit'>Add rule"
        "</button></div></form>"
    )

    body = "<h1>Rules</h1>" + switch + table + form
    return page("Rules", body, section="rules")
