"""
The Connections page: switch on the tools an agent can use.

Each connector runs a local MCP server the agent then reaches. Connecting opens
a short wizard that collects whatever the connector needs, starts it, and
verifies it by listing its tools — so "Connected" means genuinely working, not
merely registered. A service's own sign-in happens inside the connector;
Hyperium never sees the password.
"""

from __future__ import annotations

import json

from interfaces.web.layout import esc, page


def _specs(presets) -> str:
    data = {
        preset.key: {
            "name": preset.name,
            "auth": preset.auth,
            "command": preset.command,
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
    return json.dumps(data)


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

        if connected:
            action = (
                f"<button class='btn' type='button' "
                f"onclick=\"openWizard('{esc(preset.key)}')\">Reconnect</button> "
                f"<form method='post' style='display:inline;margin:0' "
                f"action='/connections/{esc(preset.key)}/disconnect'>"
                "<button class='danger' type='submit'>Disconnect</button></form>"
            )
        else:
            action = (
                f"<button class='primary' type='button' "
                f"onclick=\"openWizard('{esc(preset.key)}')\">Connect</button>"
            )

        cards.append(
            "<div class='card'>"
            f"<div class='row'><strong>{esc(preset.name)}</strong>{pill}</div>"
            f"<p class='muted' style='margin:6px 0'>{esc(preset.description)}</p>"
            f"<p class='small muted'>{esc(preset.setup)}</p>"
            f"<div class='actions'>{action}</div></div>"
        )

    body = (
        "<h1>Connections</h1>"
        "<p class='muted'>Connect the tools your business runs on. Each connector "
        "runs on this machine; connecting signs in inside the connector (never "
        "shown to Hyperium) and checks it works. Anything that sends or changes "
        "data is later held for your approval.</p>" + "".join(cards)
        + _WIZARD
        + f"<script>const CONNECTORS = {_specs(presets)};{_SCRIPT}</script>"
    )

    return page("Connections", body, section="connections")


_WIZARD = """
<div id="wiz-backdrop" class="wiz-backdrop"
  onclick="if(event.target===this)closeWizard()">
  <div class="wiz" role="dialog" aria-modal="true">
    <div class="row"><h2 id="wiz-title" style="margin:0">Connect</h2>
      <button class="btn" type="button" onclick="closeWizard()">Close</button></div>
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

_SCRIPT = r"""
let WIZ = null;
function el(id){ return document.getElementById(id); }
function openWizard(key){
  WIZ = { key: key, conf: CONNECTORS[key] };
  el('wiz-title').textContent = 'Connect ' + WIZ.conf.name;
  el('wiz-status').textContent = '';
  const body = el('wiz-body'), actions = el('wiz-actions');
  body.innerHTML = ''; actions.innerHTML = '';
  const fields = WIZ.conf.fields || [];
  fields.forEach(function(f){
    const type = f.kind === 'secret' ? 'password' : 'text';
    body.insertAdjacentHTML('beforeend',
      "<label>" + f.label + "<input data-k='" + f.key + "' type='" + type +
      "' placeholder='" + (f.placeholder || '') + "'></label>");
  });
  if (WIZ.conf.auth === 'oauth') {
    body.insertAdjacentHTML('beforeend',
      "<p class='muted small'>A browser window will open for you to sign in. " +
      "Approve access, then this will verify the connection.</p>");
  }
  if (WIZ.conf.auth === 'device') {
    body.insertAdjacentHTML('beforeend',
      "<p class='muted small'>You'll get a short code to enter at a Microsoft " +
      "sign-in page in your browser.</p>");
    addButton(actions, 'Start sign-in', startDeviceLogin);
  } else {
    addButton(actions, 'Connect', doConnect);
  }
  el('wiz-backdrop').classList.add('open');
}
function closeWizard(){ el('wiz-backdrop').classList.remove('open'); }
function addButton(host, label, fn, kind){
  const b = document.createElement('button');
  b.type = 'button'; b.textContent = label; b.className = kind || 'primary';
  b.onclick = fn; host.appendChild(b);
}
function values(){
  const out = new URLSearchParams();
  document.querySelectorAll('#wiz-body input[data-k]').forEach(function(i){
    out.append(i.getAttribute('data-k'), i.value);
  });
  return out;
}
function post(url, body){
  return fetch(url, { method:'POST',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body: body }).then(function(r){ return r.json(); });
}
function busy(msg){ const s = el('wiz-status');
  s.className='small wiz-spinner'; s.textContent = msg; }
function done(res){ const s = el('wiz-status');
  s.className = 'small ' + (res.ok ? '' : 'wiz-spinner');
  s.textContent = res.message || (res.ok ? 'Connected.' : 'Not connected.');
  if (res.ok) setTimeout(function(){ location.reload(); }, 1200);
}
function doConnect(){
  busy('Establishing and verifying… (a first run can download the connector)');
  post('/connections/' + WIZ.key + '/connect', values()).then(done)
    .catch(function(){ done({ok:false, message:'The connection attempt failed.'}); });
}
function verify(){
  busy('Verifying…');
  post('/connections/' + WIZ.key + '/verify', new URLSearchParams()).then(done)
    .catch(function(){ done({ok:false, message:'Verification failed.'}); });
}
function startDeviceLogin(){
  busy('Starting sign-in…');
  post('/connections/' + WIZ.key + '/login', values()).then(function(res){
    const body = el('wiz-body');
    if (res.ok && res.code) {
      body.insertAdjacentHTML('beforeend',
        "<p style='margin-top:12px'>Go to <a href='" + res.url + "' target='_blank'>"
        + res.url + "</a> and enter:</p><div class='code'>" + res.code + "</div>");
    }
    el('wiz-status').className = 'small muted';
    el('wiz-status').textContent = res.message || '';
    const actions = el('wiz-actions'); actions.innerHTML = '';
    addButton(actions, "I've signed in — Verify", verify);
  }).catch(function(){ done({ok:false, message:'Could not start sign-in.'}); });
}
"""
