from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from infrastructure.mcp.config import McpServerSpec


@dataclass(frozen=True)
class ConnectorField:
    """One piece of input the wizard collects before a connector can start."""

    key: str
    label: str
    kind: str = "text"  # text | secret | path
    target: str = "arg"  # arg (appended to the command) | env (an env var)
    env: str = ""  # the environment variable name, when target == "env"
    placeholder: str = ""


@dataclass(frozen=True)
class ConnectorPreset:
    """A known service an agent can be connected to, over MCP."""

    key: str
    name: str
    category: str
    description: str
    command: str
    args: list[str] = field(default_factory=list)
    #: One-time setup a person must do outside Hyperium (install, sign in).
    setup: str = ""
    #: Input the wizard asks for before connecting (a path, credentials…).
    fields: list[ConnectorField] = field(default_factory=list)
    #: How the service signs in: "none" (nothing, or the fields are enough),
    #: "oauth" (a browser opens on first run), "device" (a device-code login).
    auth: str = "none"


# A small, honest starter set. Each runs an MCP server the agent then uses; the
# service's own sign-in is a one-time step done in that server, not here. Any
# other MCP server can be added by editing the connections file.
PRESETS: dict[str, ConnectorPreset] = {
    "gmail": ConnectorPreset(
        key="gmail",
        name="Gmail",
        category="Email",
        description="Read and draft email so the agent can triage your inbox "
        "and prepare replies for you to send.",
        command="npx",
        args=["-y", "@gongrzhe/server-gmail-autoauth-mcp"],
        setup="Requires Node.js. Connecting opens a Google sign-in in your "
        "browser to authorise access; the token is stored by the connector, "
        "not by Hyperium. Sending an email is always held for your approval.",
        auth="oauth",
    ),
    "outlook": ConnectorPreset(
        key="outlook",
        name="Outlook / Microsoft 365",
        category="Email",
        description="Read Outlook mail and draft replies, so the agent can watch "
        "a folder and prepare answers for you to send.",
        command="npx",
        args=["-y", "@softeria/ms-365-mcp-server"],
        setup="Requires Node.js and a one-time Microsoft sign-in. Powers the "
        "Email page's inbox worker, which only ever drafts — never sends.",
        auth="device",
    ),
    "google-calendar": ConnectorPreset(
        key="google-calendar",
        name="Google Calendar",
        category="Calendar",
        description="See your calendar and draft events, so the agent can plan "
        "around what you already have booked.",
        command="npx",
        args=["-y", "@cocal/google-calendar-mcp"],
        setup="Requires Node.js and a one-time Google sign-in. Creating or "
        "changing an event is held for your approval.",
        auth="oauth",
    ),
    "files": ConnectorPreset(
        key="files",
        name="Local files",
        category="Files",
        description="Give the agent read/write access to a folder of your "
        "business files. No sign-in needed.",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem"],
        setup="Requires Node.js. Give it the folder to work in below. Writes are "
        "held for your approval.",
        fields=[
            ConnectorField(
                key="path",
                label="Folder to give the agent access to",
                kind="path",
                target="arg",
                placeholder=r"C:\Users\you\Business",
            )
        ],
    ),
    "xero": ConnectorPreset(
        key="xero",
        name="Xero (accounting)",
        category="Accounting",
        description="Read invoices, contacts and reports from Xero so the agent "
        "can draft invoices and answer questions about your books.",
        command="npx",
        args=["-y", "@xeroapi/xero-mcp-server"],
        setup="Requires Node.js and Xero API credentials (create a Custom "
        "Connection in the Xero developer portal). Anything that changes your "
        "accounts is held for your approval.",
        fields=[
            ConnectorField(
                key="client_id",
                label="Xero client ID",
                target="env",
                env="XERO_CLIENT_ID",
            ),
            ConnectorField(
                key="client_secret",
                label="Xero client secret",
                kind="secret",
                target="env",
                env="XERO_CLIENT_SECRET",
            ),
        ],
    ),
    "jira": ConnectorPreset(
        key="jira",
        name="Jira",
        category="Project tracking",
        description="Read, create and update Jira issues — so the agent can "
        "turn action items and plans into tickets and keep them up to date.",
        command="npx",
        args=["-y", "@aashari/mcp-server-atlassian-jira"],
        setup="Requires Node.js and an Atlassian API token. Creating or "
        "changing an issue is held for your approval.",
        fields=[
            ConnectorField(
                key="site",
                label="Atlassian site name (the part before .atlassian.net)",
                target="env",
                env="ATLASSIAN_SITE_NAME",
                placeholder="your-company",
            ),
            ConnectorField(
                key="email",
                label="Atlassian account email",
                target="env",
                env="ATLASSIAN_USER_EMAIL",
            ),
            ConnectorField(
                key="token",
                label="Atlassian API token",
                kind="secret",
                target="env",
                env="ATLASSIAN_API_TOKEN",
            ),
        ],
    ),
}


class ConnectionStore:
    """
    Which connectors are switched on, saved as an MCP config the agent can use.

    The file it writes is the same shape `load_mcp_config` reads, so an enabled
    connection is immediately usable both here and from `hyperium do --mcp`.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def enabled_keys(self) -> set[str]:
        return set(self._read().get("servers", {}))

    def enable(self, key: str, values: dict | None = None) -> None:
        if key not in PRESETS:
            raise KeyError(f"No connector preset '{key}'.")

        preset = PRESETS[key]
        values = values or {}

        args = list(preset.args)
        env: dict[str, str] = {}
        for spec in preset.fields:
            value = (values.get(spec.key) or "").strip()
            if not value:
                continue
            if spec.target == "env" and spec.env:
                env[spec.env] = value
            else:
                args.append(value)

        entry = {"command": preset.command, "args": args}
        if env:
            entry["env"] = env

        data = self._read()
        data.setdefault("servers", {})[key] = entry
        self._write(data)

    def disable(self, key: str) -> None:
        data = self._read()
        data.get("servers", {}).pop(key, None)
        self._write(data)

    def specs(self) -> dict[str, McpServerSpec]:
        specs: dict[str, McpServerSpec] = {}
        for name, spec in self._read().get("servers", {}).items():
            specs[name] = McpServerSpec(
                command=spec["command"],
                args=list(spec.get("args") or []),
                env=spec.get("env"),
            )
        return specs

    def _read(self) -> dict:
        if not self._path.is_file():
            return {"servers": {}}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
