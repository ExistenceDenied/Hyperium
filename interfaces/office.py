"""
Deliverable file types a client receives.

The Word and PowerPoint renderers now live in infrastructure (so agent tools can
produce them too) and are re-exported here for the CLI's deliverable export.
`to_eml` stays here because it renders the shared web Markdown to HTML.
"""

from __future__ import annotations

import re
from email.message import EmailMessage

from infrastructure.documents import (
    OfficeUnavailable,
    parse_blocks,
    to_docx,
    to_pptx,
)

__all__ = ["OfficeUnavailable", "parse_blocks", "to_docx", "to_pptx", "to_eml"]

_SUBJECT = re.compile(r"(?i)^\s*subject\s*:\s*(.+)$")


def to_eml(title: str, markdown: str) -> bytes:
    """
    Render a deliverable into an .eml draft an email client can open.

    No dependency — this is stdlib email. A recipient is deliberately left off:
    the file is a draft a person opens, addresses and sends. If the content
    opens with a `Subject:` line it is used; otherwise the deliverable name is.
    The body carries both a plain-text and an HTML alternative, so it renders
    well whether the client shows one or the other.
    """
    subject = title
    body = markdown

    first = markdown.lstrip().splitlines()[0] if markdown.strip() else ""
    match = _SUBJECT.match(first)
    if match:
        subject = match.group(1).strip()
        body = markdown.lstrip()[len(first) :].lstrip()

    message = EmailMessage()
    message["Subject"] = subject
    message.set_content(body)

    from interfaces.web.markdown import render

    message.add_alternative(
        f"<html><body>{render(body)}</body></html>", subtype="html"
    )

    return message.as_bytes()
