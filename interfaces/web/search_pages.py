"""Global search results, grouped by what was found."""

from __future__ import annotations

from interfaces.web.layout import esc, page


def snippet(text: str, needle: str, width: int = 120) -> str:
    """A short excerpt around the first match, so a hit shows its context."""
    if not text:
        return ""
    lowered = text.lower()
    at = lowered.find(needle.lower())
    if at == -1:
        return esc(text[:width] + ("…" if len(text) > width else ""))
    start = max(0, at - width // 3)
    end = min(len(text), at + width)
    piece = text[start:end].strip()
    return ("…" if start else "") + esc(piece) + ("…" if end < len(text) else "")


def _group(name: str, hits: list[dict]) -> str:
    rows = []
    for hit in hits:
        pill = (
            f"<span class='pill {hit['pill_kind']}'>{esc(hit['pill'])}</span> "
            if hit.get("pill")
            else ""
        )
        snip = (
            f"<div class='muted small'>{hit['snippet']}</div>"
            if hit.get("snippet")
            else ""
        )
        rows.append(
            f"<li style='margin:8px 0'>{pill}"
            f"<a href='{esc(hit['link'])}'>{esc(hit['title'])}</a>{snip}</li>"
        )
    return f"<h2>{esc(name)} <span class='muted small'>({len(hits)})</span></h2>" + (
        f"<ul style='list-style:none;padding:0'>{''.join(rows)}</ul>"
    )


def search_page(query: str, groups: list[tuple[str, list[dict]]]) -> str:
    box = (
        "<form action='/search' method='get' style='margin:8px 0 4px'>"
        "<input type='search' name='q' autofocus placeholder='Search tasks, "
        f"engagements, alerts…' value='{esc(query)}'></form>"
    )

    if not query:
        body = "<h1>Search</h1>" + box + (
            "<p class='muted'>Find past tasks, engagements, missions, memory and "
            "alerts by any word in them.</p>"
        )
        return page("Search", body, section="")

    total = sum(len(hits) for _, hits in groups)
    if total:
        found = "".join(_group(name, hits) for name, hits in groups if hits)
    else:
        found = (
            "<div class='empty'>Nothing matches "
            f"&ldquo;{esc(query)}&rdquo;.</div>"
        )

    body = (
        f"<h1>Search</h1>{box}"
        f"<p class='muted small'>{total} result"
        f"{'' if total == 1 else 's'} for &ldquo;{esc(query)}&rdquo;.</p>{found}"
    )
    return page("Search", body, section="")
