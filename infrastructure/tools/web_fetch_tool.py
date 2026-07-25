from __future__ import annotations

import urllib.error
import urllib.request

from core.tools.tool import Tool

MAX_BYTES = 100_000
USER_AGENT = "Hyperium/0.2 (local agent)"


class WebFetchTool(Tool):
    """
    Fetch the body of an http(s) URL as text.

    Read-only, but not without risk: the model chooses the URL, so a fetched
    page can carry text that tries to steer the model. Because every tool in
    the read-only set only observes — nothing here can send, write or delete —
    the blast radius is bounded to a misleading answer. Egress restrictions
    (blocking internal addresses) belong with the approval gate in Slice 2.
    """

    name = "web_fetch"
    description = (
        "Fetch the contents of an http or https URL and return the start of "
        "the response body as text. Use this to read a web page or a public "
        "API response."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "An http:// or https:// URL.",
            }
        },
        "required": ["url"],
    }

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self._timeout = timeout_seconds

    def invoke(self, arguments: dict) -> str:
        url = str(arguments.get("url", "")).strip()

        if not url.lower().startswith(("http://", "https://")):
            return "Error: only http and https URLs are supported."

        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT}
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = response.read(MAX_BYTES)
                charset = response.headers.get_content_charset() or "utf-8"
        except (urllib.error.URLError, ValueError, OSError) as error:
            return f"Error: could not fetch '{url}': {error}"

        return body.decode(charset, errors="replace")
