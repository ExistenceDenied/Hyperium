"""
The Connections page: switch on the tools an agent can use.

Each connector runs a local MCP server the agent then reaches. A service's own
sign-in happens once inside that connector — Hyperium never sees the password —
and anything that sends or changes data is held at the approval gate.
"""

from __future__ import annotations

from interfaces.web.layout import esc, page


def connections_index(presets, enabled_keys) -> str:
    cards = []

    for preset in presets:
        connected = preset.key in enabled_keys

        pill = (
            "<span class='pill ok'>Connected</span>"
            if connected
            else "<span class='pill draft'>Not connected</span>"
        )
        action = "disconnect" if connected else "connect"
        label = "Disconnect" if connected else "Connect"
        button = "danger" if connected else "primary"

        cards.append(
            "<div class='card'>"
            f"<div class='row'><strong>{esc(preset.name)}</strong>{pill}</div>"
            f"<p class='muted' style='margin:6px 0'>{esc(preset.description)}</p>"
            f"<p class='small muted'>{esc(preset.setup)}</p>"
            f"<form method='post' action='/connections/{esc(preset.key)}/{action}'>"
            f"<button class='{button}' type='submit'>{label}</button>"
            "</form></div>"
        )

    body = (
        "<h1>Connections</h1>"
        "<p class='muted'>Connect the tools your business runs on. Each "
        "connector runs on this machine; the service's sign-in happens once, "
        "inside the connector, and anything that sends or changes data is held "
        "for your approval.</p>" + "".join(cards)
    )

    return page("Connections", body, section="connections")
