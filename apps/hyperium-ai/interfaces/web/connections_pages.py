"""
The Connections page: switch on the tools an agent can use.

Each connector runs a local MCP server the agent then reaches. Connecting opens
a short wizard that collects whatever the connector needs, starts it, and
verifies it by listing its tools — so "Connected" means genuinely working, not
merely registered. A service's own sign-in happens inside the connector;
Hyperium never sees the password.

The wizard's behaviour lives in the served /app.js (the page's CSP forbids
inline scripts). This page only supplies the markup, the connector data as a
non-executable JSON block, and buttons tagged with data-connect for it to wire.
"""

from __future__ import annotations

import json

from interfaces.web.layout import esc, page


def _specs(presets) -> str:
    data = {
        preset.key: {
            "name": preset.name,
            "auth": preset.auth,
            "fields": [
                {
                    "key": field.key,
                    "label": field.label,
                    "kind": field.kind,
                    "placeholder": field.placeholder,
                }
                for field in preset.fields
            ],
        }
        for preset in presets
    }
    # Rendered inside a <script type="application/json"> block, so close any
    # accidental </script> in the data rather than trusting it not to appear.
    return json.dumps(data).replace("</", "<\\/")


def connections_index(presets, enabled_keys) -> str:
    presets = list(presets)
    cards = []

    for preset in presets:
        connected = preset.key in enabled_keys

        pill = (
            "<span class='pill ok'>Connected</span>"
            if connected
            else "<span class='pill draft'>Not connected</span>"
        )

        connect = (
            f"<button class='primary' type='button' "
            f"data-connect='{esc(preset.key)}'>"
            f"{'Reconnect' if connected else 'Connect'}</button>"
        )
        disconnect = (
            "<form method='post' style='display:inline;margin:0' "
            f"action='/connections/{esc(preset.key)}/disconnect'>"
            "<button class='danger' type='submit'>Disconnect</button></form>"
            if connected
            else ""
        )

        cards.append(
            "<div class='card'>"
            f"<div class='row'><strong>{esc(preset.name)}</strong>{pill}</div>"
            f"<p class='muted' style='margin:6px 0'>{esc(preset.description)}</p>"
            f"<p class='small muted'>{esc(preset.setup)}</p>"
            f"<div class='actions'>{connect}{disconnect}</div></div>"
        )

    body = (
        "<h1>Connections</h1>"
        "<p class='muted'>Connect the tools your business runs on. Each connector "
        "runs on this machine; connecting signs in inside the connector (never "
        "shown to Hyperium) and checks it works. Anything that sends or changes "
        "data is later held for your approval.</p>" + "".join(cards)
        + _WIZARD
        + f"<script type='application/json' id='connectors-data'>{_specs(presets)}"
        "</script>"
    )

    return page("Connections", body, section="connections")


_WIZARD = """
<div id="wiz-backdrop" class="wiz-backdrop">
  <div class="wiz" role="dialog" aria-modal="true">
    <div class="row"><h2 id="wiz-title" style="margin:0">Connect</h2>
      <button id="wiz-close" class="btn" type="button">Close</button></div>
    <div id="wiz-body"></div>
    <div id="wiz-status" class="small muted" style="margin-top:10px"></div>
    <div id="wiz-actions" class="actions"></div>
  </div>
</div>
<style>
.wiz-backdrop { display:none; position:fixed; inset:0; background:rgba(0,0,0,.45);
  z-index:50; align-items:flex-start; justify-content:center; padding:8vh 16px; }
.wiz-backdrop.open { display:flex; }
.wiz { background:var(--card); color:var(--fg); border:1px solid var(--line);
  border-radius:12px; padding:18px 20px; width:100%; max-width:460px; }
.wiz .code { font-family:ui-monospace,Consolas,monospace; font-size:20px;
  letter-spacing:2px; padding:8px 12px; background:rgba(127,127,127,.12);
  border-radius:8px; display:inline-block; margin:6px 0; }
.wiz-spinner { color:var(--warn); }
</style>
"""
