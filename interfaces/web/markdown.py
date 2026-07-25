"""
A small Markdown renderer.

Deliberately dependency-free — Hyperium's only runtime dependency is the LLM
client, and a review tool is not a good reason to add a parser.

Security note: deliverable content is written by a language model, so it is
untrusted input. Every line is HTML-escaped *before* any markup is applied,
and link targets are restricted to http/https. Nothing here ever emits raw
input into the document.
"""

from __future__ import annotations

import html
import re

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_ORDERED = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_UNORDERED = re.compile(r"^\s*[-*+]\s+(.*)$")
_RULE = re.compile(r"^\s*([-*_])\1{2,}\s*$")
_QUOTE = re.compile(r"^\s*&gt;\s?(.*)$")
_FENCE = re.compile(r"^\s*```(\w*)\s*$")
_TABLE_DIVIDER = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")

_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_SAFE_URL = re.compile(r"^(https?://|#|/)", re.IGNORECASE)


def render(text: str) -> str:
    """Render Markdown to a safe HTML fragment."""
    lines = html.escape(text or "", quote=False).replace("\r\n", "\n").split("\n")

    out: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]

        fence = _FENCE.match(line)
        if fence:
            index = _code_block(lines, index, out)
            continue

        if _RULE.match(line):
            out.append("<hr>")
            index += 1
            continue

        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            index += 1
            continue

        if _is_table(lines, index):
            index = _table(lines, index, out)
            continue

        if _UNORDERED.match(line) or _ORDERED.match(line):
            index = _list(lines, index, out)
            continue

        if _QUOTE.match(line):
            index = _quote(lines, index, out)
            continue

        if not line.strip():
            index += 1
            continue

        index = _paragraph(lines, index, out)

    return "\n".join(out)


def _code_block(lines: list[str], index: int, out: list[str]) -> int:
    language = _FENCE.match(lines[index]).group(1)
    index += 1
    body: list[str] = []

    while index < len(lines) and not _FENCE.match(lines[index]):
        body.append(lines[index])
        index += 1

    css = f' class="lang-{html.escape(language)}"' if language else ""
    out.append(f"<pre><code{css}>" + "\n".join(body) + "</code></pre>")

    return index + 1 if index < len(lines) else index


def _is_table(lines: list[str], index: int) -> bool:
    if "|" not in lines[index]:
        return False

    return index + 1 < len(lines) and bool(_TABLE_DIVIDER.match(lines[index + 1]))


def _cells(line: str) -> list[str]:
    stripped = line.strip()

    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]

    return [cell.strip() for cell in stripped.split("|")]


def _table(lines: list[str], index: int, out: list[str]) -> int:
    header = _cells(lines[index])
    index += 2

    out.append("<table><thead><tr>")
    out.extend(f"<th>{_inline(cell)}</th>" for cell in header)
    out.append("</tr></thead><tbody>")

    while index < len(lines) and "|" in lines[index] and lines[index].strip():
        out.append("<tr>")
        out.extend(f"<td>{_inline(cell)}</td>" for cell in _cells(lines[index]))
        out.append("</tr>")
        index += 1

    out.append("</tbody></table>")

    return index


def _list(lines: list[str], index: int, out: list[str]) -> int:
    ordered = bool(_ORDERED.match(lines[index]))
    tag = "ol" if ordered else "ul"
    pattern = _ORDERED if ordered else _UNORDERED

    out.append(f"<{tag}>")

    while index < len(lines):
        match = pattern.match(lines[index])

        if not match:
            break

        out.append(f"<li>{_inline(match.group(1))}</li>")
        index += 1

    out.append(f"</{tag}>")

    return index


def _quote(lines: list[str], index: int, out: list[str]) -> int:
    body: list[str] = []

    while index < len(lines):
        match = _QUOTE.match(lines[index])

        if not match:
            break

        body.append(_inline(match.group(1)))
        index += 1

    out.append("<blockquote>" + "<br>".join(body) + "</blockquote>")

    return index


def _paragraph(lines: list[str], index: int, out: list[str]) -> int:
    body: list[str] = []

    while index < len(lines) and lines[index].strip():
        if _HEADING.match(lines[index]) or _FENCE.match(lines[index]):
            break
        if _UNORDERED.match(lines[index]) or _ORDERED.match(lines[index]):
            break

        body.append(_inline(lines[index].strip()))
        index += 1

    if body:
        out.append("<p>" + "<br>".join(body) + "</p>")

    return index


def _inline(text: str) -> str:
    text = _CODE.sub(lambda m: f"<code>{m.group(1)}</code>", text)
    text = _BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", text)
    text = _ITALIC.sub(lambda m: f"<em>{m.group(1)}</em>", text)
    text = _LINK.sub(_link, text)

    return text


def _link(match: re.Match) -> str:
    label, target = match.group(1), match.group(2)

    if not _SAFE_URL.match(target):
        # javascript:, data:, and friends never become clickable.
        return f"{label} ({target})"

    safe = html.escape(target, quote=True)

    return f'<a href="{safe}" rel="noopener noreferrer">{label}</a>'
