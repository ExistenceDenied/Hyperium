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
    methodology_pages,
    pages,
    task_pages,
)
from interfaces.web.layout import error_page

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Download:
    """A response that is a file rather than a page."""

    content: str
    filename: str
    media_type: str = "text/markdown; charset=utf-8"

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
    ) -> None:
        self._service = service
        self._projects = projects
        self._missions = missions
        self._methodologies = methodologies
        self._runner = runner or BackgroundWork()
        self._resources = resources or (lambda: [])
        self._tasks = tasks
        self._connections = connections

        self._get_routes = [
            (re.compile(r"^/$"), self._engagements),
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
            (re.compile(r"^/tasks$"), self._tasks_index),
            (re.compile(r"^/tasks/new$"), self._new_task),
            (
                re.compile(r"^/tasks/(?P<key>[0-9a-f-]{36})$"),
                self._task,
            ),
            (re.compile(r"^/connections$"), self._connections_index),
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
            (re.compile(r"^/tasks$"), self._start_task),
            (
                re.compile(r"^/tasks/(?P<key>[0-9a-f-]{36})/approve$"),
                self._approve_task,
            ),
            (
                re.compile(r"^/tasks/(?P<key>[0-9a-f-]{36})/rerun$"),
                self._rerun_task,
            ),
            (
                re.compile(r"^/connections/(?P<key>[\w-]+)/connect$"),
                self._connect,
            ),
            (
                re.compile(r"^/connections/(?P<key>[\w-]+)/disconnect$"),
                self._disconnect,
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
        return 200, task_pages.tasks_index(self._require_tasks().index())

    def _new_task(self, query):
        self._require_tasks()

        return 200, task_pages.new_task()

    def _task(self, query, key):
        view = self._require_tasks().view(UUID(key))

        if view is None:
            return 404, error_page(f"No task '{key}'.")

        return 200, task_pages.task_detail(view)

    def _start_task(self, form):
        prompt = form.get("prompt", [""])[0].strip()

        if not prompt:
            return 400, error_page("A task needs a prompt.", code=400)

        task_id = self._require_tasks().start(
            prompt, allow_writes="allow_writes" in form
        )

        return 303, f"/tasks/{task_id}"

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
        view = tasks.view(UUID(key))

        if view is None:
            return 404, error_page(f"No task '{key}'.")

        # Re-runs start read-only; granting writes again is a deliberate act.
        task_id = tasks.start(view.prompt, allow_writes=False)

        return 303, f"/tasks/{task_id}"

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

    def _connect(self, form, key):
        self._require_connections().enable(key)

        return 303, "/connections"

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
            raw = self.rfile.read(length).decode("utf-8") if length else ""

            parsed = urlparse(self.path)
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
                payload = body.content.encode("utf-8")

                self.send_response(status)
                self.send_header("Content-Type", body.media_type)
                self.send_header("Content-Length", str(len(payload)))
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
                "default-src 'none'; style-src 'unsafe-inline'; "
                "form-action 'self'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt, *args):
            logger.debug("web: " + fmt, *args)

    return Handler


def serve(app: ReviewApp, host: str = "127.0.0.1", port: int = 8765):
    return ThreadingHTTPServer((host, port), build_handler(app))
