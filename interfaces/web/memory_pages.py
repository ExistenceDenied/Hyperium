"""
The Memory page: what Hyperium knows about the business.

Every agent reads this, so the work stays on-brand and consistent. It is edited
by hand here — durable facts, not per-task notes.
"""

from __future__ import annotations

from core.memory.memory_entry import CATEGORIES
from interfaces.web.layout import esc, page


def _category_select(selected: str = "") -> str:
    options = "".join(
        f"<option{' selected' if category == selected else ''}>{esc(category)}"
        "</option>"
        for category in CATEGORIES
    )
    return f"<select name='category'>{options}</select>"


def memory_index(entries) -> str:
    add = (
        "<form method='post' action='/memory'>"
        "<label>Remember something<textarea name='text' rows='2' required "
        "placeholder='e.g. Our standard day rate is £600. Our tone is warm and "
        "plain.'></textarea></label>"
        "<label>Category" + _category_select() + "</label>"
        "<div class='actions'><button class='primary' type='submit'>Add</button>"
        "</div></form>"
    )

    if entries:
        by_category: dict[str, list] = {}
        for entry in entries:
            by_category.setdefault(entry.category, []).append(entry)

        blocks = []
        for category in sorted(by_category):
            rows = "".join(
                f"<tr><td>{esc(entry.text)}</td>"
                "<td style='white-space:nowrap;width:1px'>"
                f"<a class='btn' href='/memory/{entry.id}'>Edit</a> "
                f"<form method='post' action='/memory/{entry.id}/delete' "
                "style='display:inline'>"
                "<button class='danger' type='submit'>Delete</button></form></td></tr>"
                for entry in by_category[category]
            )
            blocks.append(
                f"<h3>{esc(category)}</h3><table><tbody>{rows}</tbody></table>"
            )
        listing = "".join(blocks)
    else:
        listing = (
            "<div class='empty'>Nothing remembered yet. Add what the agents "
            "should know about your business.</div>"
        )

    body = (
        "<h1>Memory</h1>"
        "<p class='muted'>What Hyperium knows about your business. Every agent "
        "reads this, so its work stays on-brand and consistent.</p>" + add + listing
    )

    return page("Memory", body, section="memory")


def memory_edit(entry) -> str:
    parts = [
        "<p><a href='/memory'>← Memory</a></p>",
        "<h1>Edit memory</h1>",
        f"<form method='post' action='/memory/{entry.id}'>",
        "<label>Text<textarea name='text' rows='3' required>"
        + esc(entry.text)
        + "</textarea></label>",
        "<label>Category" + _category_select(entry.category) + "</label>",
        "<div class='actions'><button class='primary' type='submit'>Save</button>"
        "<a class='btn' href='/memory'>Cancel</a></div></form>",
    ]

    return page("Edit memory", "".join(parts), section="memory")
