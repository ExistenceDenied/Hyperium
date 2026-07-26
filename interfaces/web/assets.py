"""
First-party JavaScript, served as a file so the page needs no inline scripts.

The Content-Security-Policy forbids inline scripts (script-src 'self'), which is
what keeps injected markup from ever executing. So all behaviour lives here and
is loaded from /app.js, and every handler is attached with addEventListener —
never an inline onclick, which the same policy would block. Dynamic data reaches
it through a non-executable <script type="application/json"> block on the page.
"""

from __future__ import annotations

APP_JS = r"""
// ---- Alerts badge + desktop notifications, on every page ----
(function () {
  var badge = document.getElementById('alert-badge');
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
  }
  var seen;
  try { seen = JSON.parse(localStorage.getItem('seenAlerts') || '[]'); }
  catch (e) { seen = []; }
  function poll() {
    fetch('/notifications/unread.json').then(function (r) { return r.json(); })
      .then(function (data) {
        if (badge) {
          if (data.count > 0) {
            badge.textContent = data.count; badge.style.display = '';
          } else { badge.style.display = 'none'; }
        }
        (data.items || []).forEach(function (item) {
          if (seen.indexOf(item.id) !== -1) return;
          seen.push(item.id);
          if ('Notification' in window && Notification.permission === 'granted') {
            var n = new Notification('Hyperium', { body: item.text });
            n.onclick = function () { if (item.link) window.location = item.link; };
          }
        });
        try { localStorage.setItem('seenAlerts', JSON.stringify(seen.slice(-200))); }
        catch (e) {}
      }).catch(function () {});
  }
  poll();
  setInterval(poll, 15000);
})();

// ---- Connection wizard (only active on the Connect page) ----
(function () {
  var CONNECTORS = {};
  var dataEl = document.getElementById('connectors-data');
  if (!dataEl) return;
  try { CONNECTORS = JSON.parse(dataEl.textContent); } catch (e) { return; }

  var WIZ = null;
  function el(id) { return document.getElementById(id); }
  function addButton(host, label, fn, kind) {
    var b = document.createElement('button');
    b.type = 'button'; b.textContent = label; b.className = kind || 'primary';
    b.addEventListener('click', fn); host.appendChild(b);
  }
  function values() {
    var out = new URLSearchParams();
    document.querySelectorAll('#wiz-body input[data-k]').forEach(function (i) {
      out.append(i.getAttribute('data-k'), i.value);
    });
    return out;
  }
  function post(url, body) {
    return fetch(url, { method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body }).then(function (r) { return r.json(); });
  }
  function busy(msg) { var s = el('wiz-status');
    s.className = 'small wiz-spinner'; s.textContent = msg; }
  function done(res) { var s = el('wiz-status');
    s.className = 'small ' + (res.ok ? '' : 'wiz-spinner');
    s.textContent = res.message || (res.ok ? 'Connected.' : 'Not connected.');
    if (res.ok) setTimeout(function () { location.reload(); }, 1200); }
  function doConnect() {
    busy('Establishing and verifying… (a first run can download the connector)');
    post('/connections/' + WIZ.key + '/connect', values()).then(done)
      .catch(function () { done({ ok: false, message: 'The attempt failed.' }); });
  }
  function verify() {
    busy('Verifying…');
    post('/connections/' + WIZ.key + '/verify', new URLSearchParams()).then(done)
      .catch(function () { done({ ok: false, message: 'Verification failed.' }); });
  }
  function startDeviceLogin() {
    busy('Starting sign-in…');
    post('/connections/' + WIZ.key + '/login', values()).then(function (res) {
      var body = el('wiz-body');
      if (res.ok && res.code) {
        body.insertAdjacentHTML('beforeend',
          "<p style='margin-top:12px'>Go to <a href='" + res.url +
          "' target='_blank' rel='noopener'>" + res.url +
          "</a> and enter:</p><div class='code'>" + res.code + "</div>");
      }
      el('wiz-status').className = 'small muted';
      el('wiz-status').textContent = res.message || '';
      var actions = el('wiz-actions'); actions.innerHTML = '';
      addButton(actions, "I've signed in — Verify", verify);
    }).catch(function () { done({ ok: false, message: 'Could not start sign-in.' }); });
  }
  function openWizard(key) {
    WIZ = { key: key, conf: CONNECTORS[key] };
    if (!WIZ.conf) return;
    el('wiz-title').textContent = 'Connect ' + WIZ.conf.name;
    el('wiz-status').textContent = '';
    var body = el('wiz-body'), actions = el('wiz-actions');
    body.innerHTML = ''; actions.innerHTML = '';
    (WIZ.conf.fields || []).forEach(function (f) {
      var type = f.kind === 'secret' ? 'password' : 'text';
      var input = document.createElement('input');
      input.setAttribute('data-k', f.key); input.type = type;
      input.placeholder = f.placeholder || '';
      var label = document.createElement('label');
      label.textContent = f.label; label.appendChild(input);
      body.appendChild(label);
    });
    if (WIZ.conf.auth === 'oauth') {
      body.insertAdjacentHTML('beforeend', "<p class='muted small'>A browser " +
        "window will open for you to sign in. Approve access, then this " +
        "verifies the connection.</p>");
    }
    if (WIZ.conf.auth === 'device') {
      body.insertAdjacentHTML('beforeend', "<p class='muted small'>You'll get a " +
        "short code to enter at a Microsoft sign-in page in your browser.</p>");
      addButton(actions, 'Start sign-in', startDeviceLogin);
    } else {
      addButton(actions, 'Connect', doConnect);
    }
    el('wiz-backdrop').classList.add('open');
  }
  function closeWizard() { el('wiz-backdrop').classList.remove('open'); }

  document.querySelectorAll('[data-connect]').forEach(function (b) {
    b.addEventListener('click', function () {
      openWizard(b.getAttribute('data-connect'));
    });
  });
  var close = el('wiz-close');
  if (close) close.addEventListener('click', closeWizard);
  var backdrop = el('wiz-backdrop');
  if (backdrop) backdrop.addEventListener('click', function (e) {
    if (e.target === backdrop) closeWizard();
  });
})();
"""
