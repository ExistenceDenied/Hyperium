"""
A minimal multipart/form-data parser for file uploads.

The review server has no web framework, so this reads the raw request body and
pulls out both the text fields and the uploaded files. It works in bytes and
trims exactly the one CRLF the format inserts before each boundary — so binary
files, and files that legitimately end in a newline, survive intact.
"""

from __future__ import annotations

import re

_NAME = re.compile(rb'name="([^"]*)"')
_FILENAME = re.compile(rb'filename="([^"]*)"')


def boundary_of(content_type: str) -> str | None:
    """Extract the boundary token from a multipart Content-Type header."""
    match = re.search(r"boundary=([^;]+)", content_type or "")
    if not match:
        return None
    return match.group(1).strip().strip('"')


def parse(body: bytes, boundary: str) -> tuple[dict[str, str], list[tuple[str, bytes]]]:
    """Return ({field: value}, [(filename, content)]) from a multipart body."""
    fields: dict[str, str] = {}
    files: list[tuple[str, bytes]] = []
    delimiter = b"--" + boundary.encode()

    for part in body.split(delimiter):
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        if not part or part == b"--" or b"\r\n\r\n" not in part:
            continue

        header_blob, content = part.split(b"\r\n\r\n", 1)
        filename = _FILENAME.search(header_blob)
        name = _NAME.search(header_blob)

        if filename and filename.group(1):
            files.append((filename.group(1).decode("utf-8", "replace"), content))
        elif name:
            fields[name.group(1).decode("utf-8", "replace")] = content.decode(
                "utf-8", "replace"
            )

    return fields, files
