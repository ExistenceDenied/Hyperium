from __future__ import annotations

import logging
import re
import subprocess
import threading

from infrastructure.mcp.launch import resolve_argv

logger = logging.getLogger(__name__)

_URL = re.compile(r"https?://\S*(?:devicelogin|microsoft\.com)\S*", re.IGNORECASE)
_CODE = re.compile(r"\b([A-Z0-9]{4,}-?[A-Z0-9]{4,})\b")


def begin_device_login(command: str, args: list[str], timeout: float = 40.0) -> dict:
    """
    Start a connector's device-code sign-in and return the code to show.

    Runs `<command> --login`, which prints a URL and a short code the person
    enters at that URL in their own browser, then keeps polling until they
    finish — so the process is left running in the background. We read its early
    output to pull out the URL and code; the actual sign-in happens in the
    person's browser, never here.

    Best-effort: MCP servers word this prompt differently, so if a code is not
    found the raw output is returned for the person to read, and they can always
    run `<command> --login` in a terminal instead.
    """
    try:
        proc = subprocess.Popen(
            resolve_argv(command, [*args, "--login"]),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as error:  # noqa: BLE001
        logger.warning("Could not start device login: %s", error)
        return {
            "ok": False,
            "message": f"Could not start sign-in: {error}. Is Node.js installed?",
        }

    captured: list[str] = []

    def read() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            captured.append(line.rstrip())

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    reader.join(timeout)  # the process itself keeps running past this

    text = "\n".join(captured)
    url = _URL.search(text)
    code = _CODE.search(text)

    if url or code:
        return {
            "ok": True,
            "url": url.group(0) if url else "https://microsoft.com/devicelogin",
            "code": code.group(1) if code else "",
            "message": "Open the link, enter the code, and sign in. Then press "
            "Verify.",
        }

    return {
        "ok": False,
        "message": "Sign-in started but no code was detected. Run "
        f"'{command} {' '.join(args)} --login' in a terminal, then press Verify.",
        "raw": text[-500:],
    }
