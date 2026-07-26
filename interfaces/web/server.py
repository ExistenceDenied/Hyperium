"""
A local web interface for the whole engagement lifecycle.

This is an adapter, not a layer of its own: every decision is delegated to
`ProjectService` and `MissionBacklogService`. The CLI calls the same services,
so the two interfaces cannot drift apart on what anything means — which they
did, once, on approval.

Built on the standard library so that a review tool does not add a web
framework to a project whose only runtime dependency is an LLM client.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from core.missions.mission import MissionStateError
from core.missions.mission_priority import MissionPriority
from core.project.project import UnknownDeliverableError
from interfaces.web import (
    backlog_pages,
    connections_pages,
    dashboard_pages,
    email_pages,
    memory_pages,
    methodology_pages,
    notification_pages,
    pages,
    search_pages,
    task_pages,
    techniques_pages,
)
from interfaces.web.layout import error_page
from interfaces.web.multipart import boundary_of, parse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Download:
    """A response that is a file rather than a page."""

    content: str | bytes
    filename: str
    media_type: str = "text/markdown; charset=utf-8"
    #: Serve for display in the page (e.g. a script), not as an attachment.
    inline: bool = False

# Errors that are the caller's fault rather than a bug: shown, not raised.
EXPECTED = (ValueError, KeyError, FileNotFoundError, RuntimeError)


class BackgroundWork:
    """
    Runs long work off the request thread, keyed by whatever it belongs to.

    Planning and executing an engagement takes minutes against a real model.
    Holding a request open for that long looks like a hang, so the work runs
    in the background and the page reports progress.
    """

    def __init__(self) -> None:
        self._threads: dict[UUID, threading.Thread] = {}
        self._errors: dict[UUID, str] = {}
        self._lock = threading.Lock()

    def busy(self, key: UUID) -> bool:
        thread = self._threads.get(key)

        return thread is not None and thread.is_alive()

    def running(self) -> set[UUID]:
        return {key for key in self._threads if self.busy(key)}

    def error(self, key: UUID) -> str:
        return self._errors.get(key, "")

    def start(self, key: UUID, work) -> None:
        with self._lock:
            if self.busy(key):
                return

            self._errors.pop(key, None)

            thread = threading.Thread(
                target=self._run, args=(key, work), daemon=True
            )
            self._threads[key] = thread
            thread.start()

    def _run(self, key: UUID, work) -> None:
        try:
            work()
        except Exception as error:  # surfaced on the page, never swallowed
            logger.exception("Background work for %s failed.", key)
            self._errors[key] = str(error)


def _lines(value: str) -> list[str]:
    return [line.strip() for line in (value or "").splitlines() if line.strip()]





class ReviewApp:
    """
    Routing and request handling, independent of the HTTP server itself so it
    can be exercised directly in tests.
    """

    def __init__(
        self,
        service,
        projects,
        missions=None,
        methodologies=None,
        runner=None,
        resources=None,
        tasks=None,
        connections=None,
        workspace=None,
        techniques=None,
        memory=None,
        schedules=None,
        notifications=None,
        inbox=None,
        verify_connector=None,
    ) -> None:
        self._service = service
        self._projects = projects
        self._missions = missions
        self._methodologies = methodologies
        self._runner = runner or BackgroundWork()
        self._resources = resources or (lambda: [])
        self._tasks = tasks
        self._connections = connections
        self._workspace = workspace
        self._technique_repo = techniques
        self._memory = memory
        self._schedules = schedules
        self._notifications = notifications
        self._inbox = inbox
        self._verify_connector = verify_connector

        self._get_routes = [
            (re.compile(r"^/$"), self._dashboard),
            (re.compile(r"^/app\.js$"), self._app_js),
            (re.compile(r"^/search$"), self._search),
            (re.compile(r"^/engagements$"), self._engagements),
            (re.compile(r"^/notifications$"), self._notifications_index),
            (re.compile(r"^/notifications/unread\.json$"), self._notifications_unread),
            (re.compile(r"^/missions$"), self._backlog),
            (re.compile(r"^/missions/new$"), self._new_mission),
            (re.compile(r"^/missions/(?P<key>[0-9a-f-]{36})$"), self._mission),
            (
                re.compile(r"^/missions/(?P<key>[0-9a-f-]{36})/edit$"),
                self._edit_mission,
            ),
            (
                re.compile(r"^/missions/(?P<key>[0-9a-f-]{36})/delete$"),
                self._confirm_delete,
            ),
            (re.compile(r"^/methodologies$"), self._methodologies_page),
            (
                re.compile(r"^/methodologies/(?P<key>[\w-]+)$"),
                self._methodology,
            ),
            (re.compile(r"^/techniques$"), self._techniques_index),
            (re.compile(r"^/techniques/new$"), self._new_technique),
            (
                re.compile(r"^/techniques/(?P<key>[\w-]+)/template$"),
                self._technique_template,
            ),
            (
                re.compile(r"^/techniques/(?P<key>[\w-]+)$"),
                self._technique_edit,
            ),
            (re.compile(r"^/memory$"), self._memory_index),
            (
                re.compile(r"^/memory/(?P<key>[0-9a-f-]{36})$"),
                self._memory_edit,
            ),
            (re.compile(r"^/email$"), self._email_index),
            (re.compile(r"^/tasks$"), self._tasks_index),
            (re.compile(r"^/tasks/new$"), self._new_task),
            (re.compile(r"^/schedules/new$"), self._new_schedule),
            (
                re.compile(r"^/tasks/(?P<key>[0-9a-f-]{36})$"),
                self._task,
            ),
            (re.compile(r"^/connections$"), self._connections_index),
            (
                re.compile(
                    r"^/tasks/(?P<key>[0-9a-f-]{36})/file/(?P<name>[^/]+)$"
                ),
                self._task_file,
            ),
            (
                re.compile(r"^/engagement/(?P<key>[0-9a-f-]{36})$"),
                self._engagement,
            ),
            (
                re.compile(
                    r"^/engagement/(?P<key>[0-9a-f-]{36})"
                    r"/deliverable/(?P<name>[\w-]+)$"
                ),
                self._deliverable,
            ),
            (
                re.compile(
                    r"^/engagement/(?P<key>[0-9a-f-]{36})"
                    r"/deliverable/(?P<name>[\w-]+)/diff$"
                ),
                self._diff,
            ),
            (
                re.compile(
                    r"^/engagement/(?P<key>[0-9a-f-]{36})"
                    r"/deliverable/(?P<name>[\w-]+)/raw$"
                ),
                self._raw,
            ),
        ]

        self._post_routes = [
            (re.compile(r"^/missions$"), self._create_mission),
            (
                re.compile(r"^/missions/(?P<key>[0-9a-f-]{36})/edit$"),
                self._update_mission,
            ),
            (
                re.compile(r"^/missions/(?P<key>[0-9a-f-]{36})/launch$"),
                self._launch,
            ),
            (
                re.compile(r"^/missions/(?P<key>[0-9a-f-]{36})/archive$"),
                self._archive,
            ),
            (
                re.compile(r"^/missions/(?P<key>[0-9a-f-]{36})/restore$"),
                self._restore,
            ),
            (
                re.compile(r"^/missions/(?P<key>[0-9a-f-]{36})/ready$"),
                self._mark_ready,
            ),
            (
                re.compile(r"^/missions/(?P<key>[0-9a-f-]{36})/delete$"),
                self._delete,
            ),
            (
                re.compile(r"^/engagement/(?P<key>[0-9a-f-]{36})/resume$"),
                self._resume,
            ),
            (
                re.compile(r"^/tasks/(?P<key>[0-9a-f-]{36})/approve$"),
                self._approve_task,
            ),
            (
                re.compile(r"^/tasks/(?P<key>[0-9a-f-]{36})/rerun$"),
                self._rerun_task,
            ),
            (
                re.compile(r"^/tasks/(?P<key>[0-9a-f-]{36})/note$"),
                self._add_note,
            ),
            (
                re.compile(r"^/tasks/(?P<key>[0-9a-f-]{36})/improve$"),
                self._improve_task,
            ),
            (
                re.compile(r"^/tasks/(?P<key>[0-9a-f-]{36})/reply$"),
                self._reply_task,
            ),
            (re.compile(r"^/email$"), self._email_configure),
            (re.compile(r"^/notifications/read$"), self._notifications_read),
            (
                re.compile(r"^/notifications/(?P<key>[0-9a-f-]{36})/read$"),
                self._notification_read,
            ),
            (re.compile(r"^/schedules$"), self._create_schedule),
            (
                re.compile(r"^/schedules/(?P<key>[0-9a-f-]{36})/delete$"),
                self._delete_schedule,
            ),
            (
                re.compile(r"^/schedules/(?P<key>[0-9a-f-]{36})/toggle$"),
                self._toggle_schedule,
            ),
            (
                re.compile(r"^/connections/(?P<key>[\w-]+)/connect$"),
                self._connect,
            ),
            (
                re.compile(r"^/connections/(?P<key>[\w-]+)/verify$"),
                self._verify_connection,
            ),
            (
                re.compile(r"^/connections/(?P<key>[\w-]+)/login$"),
                self._connector_login,
            ),
            (
                re.compile(r"^/connections/(?P<key>[\w-]+)/disconnect$"),
                self._disconnect,
            ),
            (re.compile(r"^/techniques$"), self._create_technique),
            (
                re.compile(r"^/techniques/(?P<key>[\w-]+)/delete$"),
                self._delete_technique,
            ),
            (
                re.compile(r"^/techniques/(?P<key>[\w-]+)$"),
                self._update_technique,
            ),
            (re.compile(r"^/memory$"), self._add_memory),
            (
                re.compile(r"^/memory/(?P<key>[0-9a-f-]{36})/delete$"),
                self._delete_memory,
            ),
            (
                re.compile(r"^/memory/(?P<key>[0-9a-f-]{36})$"),
                self._update_memory,
            ),
            (
                re.compile(
                    r"^/engagement/(?P<key>[0-9a-f-]{36})"
                    r"/deliverable/(?P<name>[\w-]+)/review$"
                ),
                self._review,
            ),
            (
                re.compile(
                    r"^/engagement/(?P<key>[0-9a-f-]{36})"
                    r"/activity/(?P<name>[\w-]+)/submit$"
                ),
                self._submit,
            ),
        ]

    # ------------------------------------------------------------- routing

    def get(self, path: str, query: dict) -> tuple[int, str]:
        return self._dispatch(self._get_routes, path, query, code=404)

    def post(self, path: str, form: dict) -> tuple[int, str]:
        return self._dispatch(self._post_routes, path, form, code=400)

    def _dispatch(self, routes, path: str, data: dict, code: int):
        for pattern, handler in routes:
            match = pattern.match(path)

            if match:
                try:
                    return handler(data, **match.groupdict())
                except MissionStateError as error:
                    # The thing exists; it is the state that forbids this.
                    # Saying "not found" would be a lie.
                    return 409, error_page(str(error), code=409)
                except EXPECTED as error:
                    return code, error_page(str(error), code=code)

        return 404, error_page(f"Unknown path '{path}'.")

    # ------------------------------------------------------------ assets

    def _app_js(self, query):
        from interfaces.web.assets import APP_JS

        return 200, Download(
            APP_JS,
            "app.js",
            media_type="application/javascript; charset=utf-8",
            inline=True,
        )

    # --------------------------------------------------------- dashboard

    def _dashboard(self, query):
        views = self._tasks.index() if self._tasks else []

        counts: dict[str, int] = {}
        attention = []
        for view in views:
            counts[view.status] = counts.get(view.status, 0) + 1
            if view.status == "awaiting approval":
                attention.append((view.id, view.prompt))

        schedules = self._schedules.list() if self._schedules else []
        alerts = self._notifications.list(6) if self._notifications else []

        summary = {
            "counts": counts,
            "attention": attention,
            "recent_tasks": views[:6],
            "schedules": {
                "active": sum(1 for s in schedules if s.enabled),
                "paused": sum(1 for s in schedules if not s.enabled),
            },
            "alerts": alerts,
        }
        return 200, dashboard_pages.dashboard(summary)

    # ------------------------------------------------------------- search

    def _search(self, query):
        term = (query.get("q", [""])[0] or "").strip()
        if not term:
            return 200, search_pages.search_page("", [])

        needle = term.lower()

        def snip(text):
            return search_pages.snippet(text or "", term)

        groups: list[tuple[str, list[dict]]] = []

        # Tasks — prompt, result and notes.
        task_hits = []
        for view in self._tasks.index() if self._tasks else []:
            notes = " ".join(note.text for note in view.notes)
            hay = f"{view.prompt}\n{view.output or ''}\n{notes}".lower()
            if needle in hay:
                task_hits.append(
                    {
                        "title": view.prompt[:100],
                        "snippet": snip(view.output or view.prompt),
                        "link": f"/tasks/{view.id}",
                        "pill": view.status,
                        "pill_kind": task_pages._STATUS_PILL.get(view.status, "draft"),
                    }
                )
        groups.append(("Tasks", task_hits))

        # Engagements — the mission behind each project.
        engagement_hits = []
        if self._projects is not None:
            for project_id in self._projects.list_ids():
                try:
                    project = self._projects.load(project_id)
                except Exception:
                    continue
                title = project.mission.title
                desc = project.mission.objective.description
                if needle in f"{title}\n{desc}".lower():
                    engagement_hits.append(
                        {
                            "title": title,
                            "snippet": snip(desc),
                            "link": f"/engagement/{project.id}",
                        }
                    )
        groups.append(("Engagements", engagement_hits))

        # Missions in the backlog.
        mission_hits = []
        for mission in self._missions.list() if self._missions else []:
            desc = mission.objective.description
            if needle in f"{mission.title}\n{desc}".lower():
                mission_hits.append(
                    {
                        "title": mission.title,
                        "snippet": snip(desc),
                        "link": f"/missions/{mission.id}",
                    }
                )
        groups.append(("Missions", mission_hits))

        # Business memory.
        memory_hits = []
        for entry in self._memory.list() if self._memory else []:
            if needle in entry.text.lower():
                memory_hits.append(
                    {"title": entry.text[:100], "snippet": "", "link": "/memory"}
                )
        groups.append(("Memory", memory_hits))

        # Alerts.
        alert_hits = []
        for note in self._notifications.list(200) if self._notifications else []:
            if needle in note.text.lower():
                alert_hits.append(
                    {
                        "title": note.text,
                        "snippet": "",
                        "link": note.link or "/notifications",
                    }
                )
        groups.append(("Alerts", alert_hits))

        return 200, search_pages.search_page(term, groups)

    # ------------------------------------------------------- notifications

    def _require_notifications(self):
        if self._notifications is None:
            raise RuntimeError("This interface has no notification store.")
        return self._notifications

    def _notifications_index(self, query):
        return 200, notification_pages.notifications_index(
            self._require_notifications().list()
        )

    def _notifications_unread(self, query):
        notes = self._notifications.unread(20) if self._notifications else []
        payload = {
            "count": len(notes),
            "items": [
                {"id": str(note.id), "text": note.text, "link": note.link}
                for note in notes
            ],
        }
        return 200, json.dumps(payload)

    def _notifications_read(self, form):
        self._require_notifications().mark_all_read()
        return 303, "/notifications"

    def _notification_read(self, form, key):
        self._require_notifications().mark_read(UUID(key))
        return 303, "/notifications"

    # ------------------------------------------------------------- email

    def _require_inbox(self):
        if self._inbox is None:
            raise RuntimeError("This interface has no inbox configured.")
        return self._inbox

    def _outlook_connected(self) -> bool:
        return bool(
            self._connections and "outlook" in self._connections.enabled_keys()
        )

    def _email_index(self, query):
        inbox = self._require_inbox()
        return 200, email_pages.email_page(
            enabled=inbox.enabled,
            folder=inbox.folder,
            connected=self._outlook_connected(),
            handled=inbox.handled(),
        )

    def _email_configure(self, form):
        self._require_inbox().configure(
            enabled="enabled" in form,
            folder=form.get("folder", ["Inbox"])[0],
        )
        return 303, "/email"

    # -------------------------------------------------------- engagements

    def _engagements(self, query):
        projects = []
        unreadable = []

        for project_id in self._projects.list_ids():
            try:
                projects.append(self._projects.load(project_id))
            except Exception as error:
                # Never silently drop an engagement: a reviewer could not tell
                # the difference between "not there" and "broken".
                logger.warning("Unreadable engagement %s: %s", project_id, error)
                unreadable.append((project_id, str(error)))

        missions = self._missions.list() if self._missions else []

        return 200, pages.index(projects, missions, unreadable)

    def _engagement(self, query, key):
        project = self._projects.load(UUID(key))

        return 200, pages.engagement(
            project,
            busy=self._runner.busy(project.id),
            error=self._runner.error(project.id),
        )

    def _deliverable(self, query, key, name):
        project = self._projects.load(UUID(key))

        try:
            deliverable = project.deliverable(name)
        except UnknownDeliverableError as error:
            return 404, error_page(str(error))

        version = query.get("version")

        return 200, pages.deliverable_view(
            project, deliverable, int(version[0]) if version else None
        )

    def _diff(self, query, key, name):
        project = self._projects.load(UUID(key))

        try:
            deliverable = project.deliverable(name)
        except UnknownDeliverableError as error:
            return 404, error_page(str(error))

        versions = [v.version for v in deliverable.versions]

        if len(versions) < 2:
            return 404, error_page(
                "This deliverable has only one version; there is nothing to "
                "compare."
            )

        after = int(query.get("to", [versions[-1]])[0])
        before = int(
            query.get("from", [max(v for v in versions if v < after)])[0]
        )

        return 200, pages.diff_view(project, deliverable, before, after)

    def _review(self, form, key, name):
        project = self._projects.load(UUID(key))
        decision = form.get("decision", [""])[0]
        note = form.get("note", [""])[0].strip() or None

        if decision == "approve":
            self._service.approve(project, name, note=note)
        elif decision == "reject":
            self._service.request_changes(project, name, note=note or "")
        else:
            return 400, error_page("Unknown review decision.", code=400)

        return 303, f"/engagement/{project.id}"

    def _submit(self, form, key, name):
        project = self._projects.load(UUID(key))
        content = form.get("content", [""])[0]

        self._service.submit_work(project, name, content)

        return 303, f"/engagement/{project.id}"

    def _resume(self, form, key):
        project = self._projects.load(UUID(key))

        self._runner.start(
            project.id,
            lambda: self._service.resume(self._projects.load(project.id)),
        )

        return 303, f"/engagement/{project.id}"

    # -------------------------------------------------------------- tasks

    def _require_tasks(self):
        if self._tasks is None:
            raise RuntimeError("This interface has no task runner configured.")

        return self._tasks

    def _tasks_index(self, query):
        missions = self._missions.list() if self._missions else []
        schedules = self._schedules.list() if self._schedules else []
        return 200, task_pages.tasks_index(
            self._require_tasks().index(), missions, schedules
        )

    def _new_task(self, query):
        self._require_tasks()

        techniques = self._technique_repo.list() if self._technique_repo else []
        methodologies = self._methodologies.all() if self._methodologies else []

        return 200, task_pages.new_task(techniques, methodologies)

    def _task(self, query, key):
        view = self._require_tasks().view(UUID(key))

        if view is None:
            return 404, error_page(f"No task '{key}'.")

        return 200, task_pages.task_detail(view)

    def _task_file(self, query, key, name):
        import mimetypes
        from pathlib import Path
        from urllib.parse import unquote

        tasks = self._require_tasks()
        task_id = UUID(key)

        # Decode %20 etc. from the URL; Path(name).name keeps the download
        # inside the task's own folder even if the name contains separators.
        path = tasks.folder(task_id) / Path(unquote(name)).name

        if not path.is_file():
            return 404, error_page(f"No file '{name}' for this task.")

        media = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

        return 200, Download(
            content=path.read_bytes(), filename=path.name, media_type=media
        )

    def upload(self, path: str, fields, files) -> tuple[int, str]:
        """Handle a multipart POST: a new task, files for a task, or a template."""
        if path == "/tasks":
            prompt = (fields.get("prompt") or "").strip()
            if not prompt:
                return 400, error_page("A task needs a prompt.", code=400)
            tasks = self._require_tasks()
            launch = tasks.queue if "queue" in fields else tasks.start
            task_id = launch(
                prompt,
                uploads=files,
                priority=(fields.get("priority") or "medium").strip(),
                technique=(fields.get("technique") or "").strip(),
                methodology=(fields.get("methodology") or "").strip(),
            )
            return 303, f"/tasks/{task_id}"

        match = re.match(r"^/tasks/([0-9a-f-]{36})/upload$", path)
        if match:
            self._require_tasks().save_uploads(UUID(match.group(1)), files)
            return 303, f"/tasks/{match.group(1)}"

        technique = re.match(r"^/techniques/([\w-]+)/template$", path)
        if technique and files:
            self._require_technique_repo().save_template(
                technique.group(1), files[0][1]
            )
            return 303, f"/techniques/{technique.group(1)}"

        return 404, error_page(f"Unknown path '{path}'.")

    def _approve_task(self, form, key):
        decision = form.get("decision", [""])[0]

        if decision not in ("approve", "reject"):
            return 400, error_page("Unknown approval decision.", code=400)

        self._require_tasks().approve(
            UUID(key),
            approved=decision == "approve",
            reason=f"{decision}d via the web UI",
        )

        return 303, f"/tasks/{key}"

    def _rerun_task(self, form, key):
        tasks = self._require_tasks()
        task_id = UUID(key)
        view = tasks.view(task_id)

        if view is None:
            return 404, error_page(f"No task '{key}'.")

        # Re-run in place: same folder, so any files uploaded to the task are
        # used and its outputs update rather than starting a fresh task.
        tasks.start(
            view.prompt,
            task_id=task_id,
            priority=view.priority,
            technique=view.technique,
            methodology=view.methodology,
        )

        return 303, f"/tasks/{task_id}"

    def _improve_task(self, form, key):
        self._require_tasks().suggest_improvements(UUID(key))
        return 303, f"/tasks/{key}"

    def _reply_task(self, form, key):
        message = form.get("message", [""])[0].strip()
        if message:
            self._require_tasks().follow_up(UUID(key), message)
        return 303, f"/tasks/{key}"

    # ----------------------------------------------------------- schedules

    def _require_schedules(self):
        if self._schedules is None:
            raise RuntimeError("This interface has no schedule store.")
        return self._schedules

    def _new_schedule(self, query):
        self._require_schedules()
        techniques = self._technique_repo.list() if self._technique_repo else []
        methodologies = self._methodologies.all() if self._methodologies else []
        return 200, task_pages.new_schedule(techniques, methodologies)

    def _create_schedule(self, form):
        prompt = form.get("prompt", [""])[0].strip()
        if not prompt:
            return 400, error_page("A schedule needs a prompt.", code=400)
        self._require_schedules().add(
            prompt,
            every_hours=int(form.get("every_hours", ["24"])[0]),
            priority=form.get("priority", ["medium"])[0],
            technique=form.get("technique", [""])[0],
            methodology=form.get("methodology", [""])[0],
        )
        return 303, "/tasks"

    def _toggle_schedule(self, form, key):
        schedule = self._require_schedules().get(UUID(key))
        if schedule is not None:
            self._schedules.set_enabled(UUID(key), not schedule.enabled)
        return 303, "/tasks"

    def _delete_schedule(self, form, key):
        self._require_schedules().delete(UUID(key))
        return 303, "/tasks"

    def _add_note(self, form, key):
        note = form.get("note", [""])[0].strip()

        if note:
            self._require_tasks().add_note(UUID(key), note)

        return 303, f"/tasks/{key}"

    # -------------------------------------------------------- connections

    def _require_connections(self):
        if self._connections is None:
            raise RuntimeError("This interface has no connections configured.")

        return self._connections

    def _connections_index(self, query):
        from infrastructure.connectors import PRESETS

        store = self._require_connections()

        return 200, connections_pages.connections_index(
            list(PRESETS.values()), store.enabled_keys()
        )

    def _verifier(self):
        if self._verify_connector is not None:
            return self._verify_connector
        from infrastructure.mcp.verify import verify_connector

        return verify_connector

    def _first_value(self, form: dict) -> dict:
        # Form values arrive as {name: [value]}; flatten for connector fields.
        return {name: (values[0] if values else "") for name, values in form.items()}

    def _connect(self, form, key):
        """Save a connector's input, start it, and verify — the wizard's core."""
        from infrastructure.connectors import PRESETS

        if key not in PRESETS:
            return 404, error_page(f"No connector '{key}'.")

        store = self._require_connections()
        store.enable(key, self._first_value(form))
        result = self._verifier()(store.specs()[key])

        if not result.ok:
            # Leave it registered so the person can retry Verify after signing
            # in, but report honestly that it is not usable yet.
            return 200, json.dumps(
                {"ok": False, "message": result.message, "tools": 0}
            )
        return 200, json.dumps(
            {"ok": True, "message": result.message, "tools": result.tools}
        )

    def _verify_connection(self, form, key):
        store = self._require_connections()
        specs = store.specs()
        if key not in specs:
            return 200, json.dumps(
                {"ok": False, "message": "Not connected yet.", "tools": 0}
            )
        result = self._verifier()(specs[key])
        return 200, json.dumps(
            {"ok": result.ok, "message": result.message, "tools": result.tools}
        )

    def _connector_login(self, form, key):
        """Begin a device-code sign-in and return the code for the user."""
        from infrastructure.connectors import PRESETS
        from infrastructure.mcp.device_login import begin_device_login

        preset = PRESETS.get(key)
        if preset is None or preset.auth != "device":
            return 200, json.dumps(
                {"ok": False, "message": "This connector has no device sign-in."}
            )
        self._require_connections().enable(key, self._first_value(form))
        info = begin_device_login(preset.command, list(preset.args))
        return 200, json.dumps(info)

    def _disconnect(self, form, key):
        self._require_connections().disable(key)

        return 303, "/connections"

    # ------------------------------------------------------------ backlog

    def _require_backlog(self):
        if self._missions is None:
            raise RuntimeError("This interface has no mission backlog.")

        return self._missions

    def _catalogue(self):
        return self._methodologies.all() if self._methodologies else []

    def _backlog(self, query):
        backlog = self._require_backlog()
        show_archived = query.get("all", ["0"])[0] == "1"

        return 200, backlog_pages.backlog(
            backlog.list(include_archived=show_archived),
            show_archived=show_archived,
            launching=self._runner.running(),
        )

    def _mission(self, query, key):
        backlog = self._require_backlog()
        mission = backlog.get(UUID(key))

        project = None
        project_error = ""

        if mission.project_id:
            try:
                project = self._projects.load(mission.project_id)
            except Exception as error:
                # Say so, rather than showing a mission with no deliverables.
                project_error = str(error)

        return 200, backlog_pages.mission_detail(
            mission,
            self._catalogue(),
            project=project,
            launching=self._runner.busy(mission.id),
            error=self._runner.error(mission.id),
            project_error=project_error,
        )

    def _confirm_delete(self, query, key):
        backlog = self._require_backlog()

        return 200, backlog_pages.confirm_delete(backlog.get(UUID(key)))

    def _mark_ready(self, form, key):
        backlog = self._require_backlog()
        backlog.mark_ready(UUID(key))

        return 303, f"/missions/{key}"

    def _raw(self, query, key, name):
        """The deliverable as its own file, which is what a client receives."""
        project = self._projects.load(UUID(key))

        try:
            deliverable = project.deliverable(name)
        except UnknownDeliverableError as error:
            return 404, error_page(str(error))

        requested = query.get("version")
        version = deliverable.latest_version()

        if requested:
            matches = [
                item
                for item in deliverable.versions
                if item.version == int(requested[0])
            ]

            if not matches:
                return 404, error_page(
                    f"No version {requested[0]} of '{deliverable.key}'."
                )

            version = matches[0]

        if version is None:
            return 404, error_page(
                f"'{deliverable.key}' has no content to download yet."
            )

        return 200, Download(version.content, version.filename)

    def _new_mission(self, query):
        self._require_backlog()

        return 200, backlog_pages.mission_form(methodologies=self._catalogue())

    def _edit_mission(self, query, key):
        backlog = self._require_backlog()

        return 200, backlog_pages.mission_form(
            mission=backlog.for_editing(UUID(key)),
            methodologies=self._catalogue(),
        )

    def _form_values(self, form) -> dict:
        return {
            name: form.get(name, [""])[0]
            for name in (
                "title",
                "objective",
                "criteria",
                "constraints",
                "priority",
                "methodology",
                "stakeholders",
            )
        }

    def _create_mission(self, form):
        backlog = self._require_backlog()
        values = self._form_values(form)

        try:
            mission = backlog.create(
                title=values["title"],
                objective=values["objective"],
                priority=MissionPriority.parse(values["priority"] or "medium"),
                criteria=_lines(values["criteria"]),
                constraints=_lines(values["constraints"]),
                stakeholders=_lines(values["stakeholders"]),
                methodology=values["methodology"] or None,
            )
        except ValueError as error:
            # Re-render with what they typed rather than losing it.
            return 400, backlog_pages.mission_form(
                methodologies=self._catalogue(),
                error=str(error),
                values=values,
            )

        return 303, f"/missions/{mission.id}"

    def _update_mission(self, form, key):
        backlog = self._require_backlog()
        values = self._form_values(form)
        mission = backlog.get(UUID(key))

        try:
            backlog.update(
                mission.id,
                title=values["title"],
                objective=values["objective"],
                priority=MissionPriority.parse(values["priority"] or "medium"),
                clear_criteria=True,
                add_criteria=_lines(values["criteria"]),
                clear_constraints=True,
                add_constraints=_lines(values["constraints"]),
                clear_stakeholders=True,
                add_stakeholders=_lines(values["stakeholders"]),
                methodology=values["methodology"],
            )
        except ValueError as error:
            return 400, backlog_pages.mission_form(
                mission=mission,
                methodologies=self._catalogue(),
                error=str(error),
                values=values,
            )

        return 303, f"/missions/{mission.id}"

    def _launch(self, form, key):
        backlog = self._require_backlog()
        mission = backlog.get(UUID(key))
        chosen = form.get("methodology", [""])[0].strip()

        if chosen and chosen != (mission.methodology or ""):
            backlog.update(mission.id, methodology=chosen)

        self._runner.start(
            mission.id,
            lambda: backlog.launch(mission.id, resources=self._resources()),
        )

        return 303, f"/missions/{mission.id}"

    def _archive(self, form, key):
        backlog = self._require_backlog()
        backlog.archive(UUID(key))

        return 303, f"/missions/{key}"

    def _restore(self, form, key):
        backlog = self._require_backlog()
        backlog.restore(UUID(key))

        return 303, f"/missions/{key}"

    def _delete(self, form, key):
        backlog = self._require_backlog()
        backlog.delete(UUID(key))

        return 303, "/missions"

    # ------------------------------------------------------ methodologies

    def _methodologies_page(self, query):
        if self._methodologies is None:
            return 404, error_page("No methodology library is configured.")

        return 200, methodology_pages.catalogue(
            self._methodologies.all(),
            self._methodologies.techniques(),
        )

    def _methodology(self, query, key):
        if self._methodologies is None:
            return 404, error_page("No methodology library is configured.")

        return 200, methodology_pages.methodology_detail(
            self._methodologies.get(key),
            self._methodologies.techniques(),
        )

    # --------------------------------------------------------- techniques

    def _require_technique_repo(self):
        if self._technique_repo is None:
            raise RuntimeError("This interface has no technique library.")

        return self._technique_repo

    def _techniques_index(self, query):
        return 200, techniques_pages.techniques_index(
            self._require_technique_repo().list()
        )

    def _new_technique(self, query):
        self._require_technique_repo()
        return 200, techniques_pages.technique_form()

    def _technique_edit(self, query, key):
        technique = self._require_technique_repo().get(key)
        if technique is None:
            return 404, error_page(f"No technique '{key}'.")
        return 200, techniques_pages.technique_form(technique)

    def _create_technique(self, form):
        return self._save_technique(form, form.get("key", [""])[0])

    def _update_technique(self, form, key):
        return self._save_technique(form, key)

    def _save_technique(self, form, key):
        from core.methodologies.technique import Technique

        technique = Technique(
            key=key.strip().lower(),
            name=form.get("name", [""])[0].strip(),
            description=form.get("description", [""])[0].strip(),
            guidance=form.get("guidance", [""])[0].strip(),
            capabilities=frozenset(
                cap.strip().upper() for cap in form.get("capabilities", [])
            ),
        )
        # save() validates capabilities; a bad one becomes a 400 via _dispatch.
        self._require_technique_repo().save(technique)

        return 303, f"/techniques/{technique.key}"

    def _delete_technique(self, form, key):
        self._require_technique_repo().delete(key)
        return 303, "/techniques"

    def _technique_template(self, query, key):
        data = self._require_technique_repo().template_bytes(key)
        if data is None:
            return 404, error_page(f"No template for technique '{key}'.")

        return 200, Download(
            content=data,
            filename=f"{key}.md",
            media_type="text/markdown; charset=utf-8",
        )

    # ------------------------------------------------------------- memory

    def _require_memory(self):
        if self._memory is None:
            raise RuntimeError("This interface has no memory store.")
        return self._memory

    def _memory_index(self, query):
        return 200, memory_pages.memory_index(self._require_memory().list())

    def _memory_edit(self, query, key):
        entry = self._require_memory().get(UUID(key))
        if entry is None:
            return 404, error_page("No such memory entry.")
        return 200, memory_pages.memory_edit(entry)

    def _add_memory(self, form):
        text = form.get("text", [""])[0].strip()
        if text:
            self._require_memory().add(text, form.get("category", ["general"])[0])
        return 303, "/memory"

    def _update_memory(self, form, key):
        self._require_memory().update(
            UUID(key),
            form.get("text", [""])[0],
            form.get("category", ["general"])[0],
        )
        return 303, "/memory"

    def _delete_memory(self, form, key):
        self._require_memory().delete(UUID(key))
        return 303, "/memory"


def build_handler(app: ReviewApp):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Hyperium"

        def do_GET(self):  # noqa: N802 - required by BaseHTTPRequestHandler
            parsed = urlparse(self.path)
            status, body = app.get(parsed.path, parse_qs(parsed.query))
            self._respond(status, body)

        def do_POST(self):  # noqa: N802
            if not self._same_origin():
                # The server has no authentication, so a page you visit
                # elsewhere could otherwise post to it. Reject anything that
                # did not originate here.
                self._respond(
                    403,
                    error_page(
                        "Refused: this request came from another site.",
                        code=403,
                    ),
                )
                return

            length = int(self.headers.get("Content-Length", 0) or 0)
            content_type = self.headers.get("Content-Type", "")
            parsed = urlparse(self.path)

            if content_type.startswith("multipart/form-data"):
                # Read raw bytes — an upload may be binary — and pull the parts.
                raw_bytes = self.rfile.read(length) if length else b""
                boundary = boundary_of(content_type)
                fields, files = parse(raw_bytes, boundary) if boundary else ({}, [])
                status, body = app.upload(parsed.path, fields, files)
                self._respond(status, body)
                return

            raw = self.rfile.read(length).decode("utf-8") if length else ""
            status, body = app.post(parsed.path, parse_qs(raw))
            self._respond(status, body)

        def _same_origin(self) -> bool:
            """
            Compare the request's origin against the Host it was sent to.

            Comparing against a set computed at startup was wrong: binding to
            port 0 produced a server that refused every one of its own posts.
            The Host header is always the address the browser actually used.
            """
            host = self.headers.get("Host")

            if not host:
                return False

            for header in ("Origin", "Referer"):
                value = self.headers.get(header)

                if value:
                    return urlparse(value).netloc == host

            # A form post from the same document may send neither header.
            return True

        def _respond(self, status: int, body: str) -> None:
            if status == 303:
                self.send_response(303)
                self.send_header("Location", body)
                self.end_headers()
                return

            if isinstance(body, Download):
                payload = (
                    body.content
                    if isinstance(body.content, bytes)
                    else body.content.encode("utf-8")
                )

                self.send_response(status)
                self.send_header("Content-Type", body.media_type)
                self.send_header("Content-Length", str(len(payload)))
                if not body.inline:
                    self.send_header(
                        "Content-Disposition",
                        f'attachment; filename="{body.filename}"',
                    )
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(payload)
                return

            payload = body.encode("utf-8")

            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            self.send_header(
                "Content-Security-Policy",
                # Scripts only from this origin (a served /app.js file, never
                # inline), and fetch only back to this origin. Inline styles
                # stay allowed; everything else is denied.
                "default-src 'none'; script-src 'self'; connect-src 'self'; "
                "style-src 'unsafe-inline'; form-action 'self'; "
                "frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt, *args):
            logger.debug("web: " + fmt, *args)

    return Handler


def serve(app: ReviewApp, host: str = "127.0.0.1", port: int = 8765):
    return ThreadingHTTPServer((host, port), build_handler(app))
