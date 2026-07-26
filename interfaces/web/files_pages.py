"""
The Files page: upload files an agent can use.

Uploads land in the workspace, where the agents' read tools are scoped, so a
task or engagement can read them by name (for example `uploads/invoice.xlsx`).
"""

from __future__ import annotations

from interfaces.web.layout import esc, page

UPLOADS = "uploads"


def files_index(files) -> str:
    """`files` is a list of (name, size_bytes)."""
    if files:
        rows = "".join(
            f"<tr><td><code>{UPLOADS}/{esc(name)}</code></td>"
            f"<td class='small muted'>{size} bytes</td></tr>"
            for name, size in files
        )
        listing = (
            "<table><thead><tr><th>Reference it as</th><th>Size</th></tr>"
            f"</thead><tbody>{rows}</tbody></table>"
        )
    else:
        listing = "<div class='empty'>No files uploaded yet.</div>"

    body = (
        "<h1>Files</h1>"
        "<p class='muted'>Upload files here and an agent can use them. In a "
        f"task or mission, refer to a file as <code>{UPLOADS}/&lt;name&gt;</code> "
        "— for example <em>“Summarise uploads/report.pdf”</em>.</p>"
        "<form method='post' action='/files' enctype='multipart/form-data'>"
        "<label>Choose files"
        "<input type='file' name='files' multiple></label>"
        "<div class='actions'><button class='primary' type='submit'>Upload"
        "</button></div></form>" + listing
    )

    return page("Files", body, section="files")
