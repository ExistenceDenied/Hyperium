"""
Shared page chrome: styles, escaping, navigation.

Every view builds on this, so the interface looks like one product rather than
several pages that happen to share a server.
"""

from __future__ import annotations

import html

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
header.top { border-bottom:1px solid var(--line); background:var(--card);
  position:sticky; top:0; z-index:5; }
header.top .wrap { padding:12px 20px; display:flex; gap:20px; align-items:center;
  flex-wrap:wrap; }
header.top strong { font-size:17px; margin-right:4px; }
nav a { text-decoration:none; padding:5px 2px; border-bottom:2px solid transparent;
  color:var(--muted); font-weight:500; }
nav a.on { color:var(--fg); border-bottom-color:var(--accent); }
nav { display:flex; gap:18px; }
h1 { font-size:24px; margin:22px 0 6px; }
h2 { font-size:19px; margin:26px 0 8px; }
h3 { font-size:16px; margin:18px 0 6px; }
.muted { color:var(--muted); }
.small { font-size:13px; }
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
button.primary, .btn.primary { background:var(--accent); border-color:var(--accent);
  color:#fff; }
button.danger { color:var(--bad); border-color:var(--bad); }
input, select, textarea { width:100%; font:inherit; padding:8px 9px;
  border-radius:8px; border:1px solid var(--line); background:var(--bg);
  color:var(--fg); }
label { display:block; margin:12px 0 4px; font-weight:600; font-size:14px; }
label .hint { font-weight:400; color:var(--muted); font-size:13px; }
.grid2 { display:grid; grid-template-columns:1fr 1fr; gap:0 16px; }
@media (max-width:640px) { .grid2 { grid-template-columns:1fr; } }
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
.banner.bad { border-left-color:var(--bad); }
.actions { display:flex; gap:10px; flex-wrap:wrap; margin-top:12px; }
.empty { text-align:center; padding:36px 20px; color:var(--muted); }
"""

_NAV = (
    ("/", "Engagements", "engagements"),
    ("/tasks", "Tasks", "tasks"),
    ("/files", "Files", "files"),
    ("/connections", "Connect", "connections"),
    ("/missions", "Backlog", "backlog"),
    ("/methodologies", "Methodologies", "methodologies"),
)


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def page(title: str, body: str, refresh: bool = False, section: str = "") -> str:
    meta = '<meta http-equiv="refresh" content="4">' if refresh else ""

    nav = "".join(
        f"<a href='{href}' class='{'on' if key == section else ''}'>{label}</a>"
        for href, label, key in _NAV
    )

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"{meta}<title>{esc(title)} · Hyperium</title><style>{STYLE}</style>"
        "</head><body><header class='top'><div class='wrap'>"
        "<strong><a href='/' style='text-decoration:none;color:inherit'>"
        f"Hyperium</a></strong><nav>{nav}</nav></div></header>"
        f"<div class='wrap'>{body}</div></body></html>"
    )


def banner(message: str, bad: bool = False) -> str:
    return f"<div class='banner{' bad' if bad else ''}'>{message}</div>"


def error_page(message: str, code: int = 404) -> str:
    return page(
        "Not found" if code == 404 else "Error",
        f"<h1>{code}</h1><p class='muted'>{esc(message)}</p>"
        "<p><a href='/'>Back to engagements</a></p>",
    )
