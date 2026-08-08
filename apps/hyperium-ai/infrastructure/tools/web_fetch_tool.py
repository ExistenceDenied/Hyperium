from __future__ import annotations

import ipaddress
import os
import socket
import urllib.error
import urllib.request
from urllib.parse import urlparse

from core.tools.tool import Tool

MAX_BYTES = 100_000
USER_AGENT = "Hyperium/0.2 (local agent)"


def _blocked_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def _allowed_hosts() -> list[str]:
    raw = os.environ.get("HYPERIUM_WEB_FETCH_ALLOW", "")
    return [h.strip().lower() for h in raw.split(",") if h.strip()]


def _reject(url: str) -> str | None:
    """Return an error string if the URL must not be fetched, else None."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "only http and https URLs are supported"

    host = (parsed.hostname or "").lower()
    if not host:
        return "the URL has no host"

    # An egress allowlist, when set, is the strongest control: only these hosts
    # (or their subdomains) may ever be fetched, which stops data exfiltration
    # to an attacker's server via a fetched URL.
    allow = _allowed_hosts()
    if allow and not any(host == a or host.endswith("." + a) for a in allow):
        return f"'{host}' is not in the web-fetch allowlist"

    # Block internal/loopback/link-local targets — no SSRF into localhost, the
    # cloud metadata endpoint, or the private network — checking every resolved
    # address so a public name that resolves inward is still blocked.
    try:
        infos = socket.getaddrinfo(host, parsed.port or None)
    except socket.gaierror:
        return f"could not resolve '{host}'"
    for info in infos:
        if _blocked_ip(info[4][0]):
            return f"'{host}' resolves to a disallowed (internal) address"
    return None


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Re-validate every redirect target, so a redirect cannot reach inward."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        reason = _reject(newurl)
        if reason:
            raise urllib.error.URLError(f"blocked redirect: {reason}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class WebFetchTool(Tool):
    """
    Fetch the body of an http(s) URL as text.

    Read-only, but the model chooses the URL, so egress is filtered: internal,
    loopback and link-local addresses are blocked (no SSRF), redirects are
    re-checked, and an optional HYPERIUM_WEB_FETCH_ALLOW allowlist can restrict
    fetches to named hosts — the defence against a prompt-injected task
    exfiltrating data through a fetched URL.
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
        self._opener = urllib.request.build_opener(_SafeRedirect())

    def invoke(self, arguments: dict) -> str:
        url = str(arguments.get("url", "")).strip()

        reason = _reject(url)
        if reason:
            return f"Error: {reason}."

        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                body = response.read(MAX_BYTES)
                charset = response.headers.get_content_charset() or "utf-8"
        except (urllib.error.URLError, ValueError, OSError) as error:
            return f"Error: could not fetch '{url}': {error}"

        return body.decode(charset, errors="replace")
