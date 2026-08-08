"""
Export an engagement's deliverables as one self-contained document.

Markdown on disk is not what a client receives. This binds every produced
deliverable into a single, styled, print-ready HTML file — a cover, a table of
contents, and each deliverable as its own section that starts on a new page
when printed. No dependency: it reuses the same Markdown renderer the web
review UI uses. Open it in a browser to present it, or print to PDF to hand it
over. Native PowerPoint / Word are a further step that would add a dependency.
"""

from __future__ import annotations

from datetime import date

from interfaces.web.layout import esc
from interfaces.web.markdown import render

_STYLE = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; color: #16181d;
  font: 15px/1.65 ui-sans-serif, system-ui, "Segoe UI", Roboto, sans-serif; }
.cover { min-height: 60vh; display: flex; flex-direction: column;
  justify-content: center; padding: 12vh 8vw; border-bottom: 2px solid #1a3b7a; }
.cover h1 { font-size: 40px; margin: 0 0 12px; color: #1a3b7a; }
.muted { color: #5a6272; } .small { font-size: 13px; }
main { max-width: 820px; margin: 0 auto; padding: 24px 24px 80px; }
.toc { margin: 24px 0 8px; }
.toc a { color: #1a3b7a; text-decoration: none; }
section { page-break-before: always; padding-top: 8px; }
section h1 { font-size: 26px; color: #1a3b7a; border-bottom: 1px solid #dfe3ea;
  padding-bottom: 6px; }
.desc { color: #5a6272; font-style: italic; }
h2 { font-size: 20px; margin-top: 26px; } h3 { font-size: 16px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th, td { border: 1px solid #d7dbe3; padding: 6px 9px; text-align: left;
  vertical-align: top; }
th { background: #f2f4f8; }
pre { background: #f5f6f8; padding: 12px; border-radius: 6px; overflow-x: auto; }
code { font-family: ui-monospace, Consolas, monospace; font-size: 13px; }
blockquote { border-left: 3px solid #cfd5df; margin: 8px 0; padding: 2px 12px;
  color: #5a6272; }
@media print { .toc { page-break-after: always; } }
"""


def build_html_pack(project) -> str:
    """Render every deliverable that has content into one bound document."""
    title = project.mission.title
    toc: list[str] = []
    sections: list[str] = []

    for deliverable in project.deliverables:
        version = deliverable.latest_version()

        if version is None:
            continue

        anchor = esc(deliverable.key)
        toc.append(f"<li><a href='#{anchor}'>{esc(deliverable.name)}</a></li>")

        description = (
            f"<p class='desc'>{esc(deliverable.description)}</p>"
            if deliverable.description
            else ""
        )
        sections.append(
            f"<section id='{anchor}'><h1>{esc(deliverable.name)}</h1>"
            f"{description}<div class='doc'>{render(version.content)}</div></section>"
        )

    if not sections:
        sections = ["<p>This engagement has no delivered content yet.</p>"]

    contents = (
        f"<nav class='toc'><h2>Contents</h2><ol>{''.join(toc)}</ol></nav>"
        if toc
        else ""
    )

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{esc(title)}</title><style>{_STYLE}</style></head><body>"
        f"<div class='cover'><h1>{esc(title)}</h1>"
        f"<p class='muted'>{esc(project.mission.objective.description)}</p>"
        f"<p class='muted small'>Prepared by Hyperium · {date.today().isoformat()}"
        "</p></div>"
        f"<main>{contents}{''.join(sections)}</main>"
        "</body></html>"
    )
