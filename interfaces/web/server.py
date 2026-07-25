"""
A local review server.

This is an adapter, not a layer of its own: every decision is delegated to
ProjectService and the domain. It exists because reviewing a generated
document in a terminal is the weakest part of the human loop.

Built on the standard library so that a review tool does not add a web
framework to a project whose only runtime dependency is an LLM client.
"""

from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from core.project.project import UnknownDeliverableError
from interfaces.web import pages

logger = logging.getLogger(__name__)


class EngagementRunner:
    """
    Runs the engine off the request thread.

    A resume can take minutes against a real model. Blocking the browser for
    that long looks like a hang, so the work happens in the background and the
    page reports progress instead.
    """

    def __init__(self) -> None:
        self._threads: dict[UUID, threading.Thread] = {}
        self._errors: dict[UUID, str] = {}
        self._lock = threading.Lock()

    def busy(self, project_id: UUID) -> bool:
        thread = self._threads.get(project_id)

        return thread is not None and thread.is_alive()

    def error(self, project_id: UUID) -> str:
        return self._errors.get(project_id, "")

    def start(self, project_id: UUID, work) -> None:
        with self._lock:
            if self.busy(project_id):
                return

            self._errors.pop(project_id, None)

            thread = threading.Thread(
                target=self._run,
                args=(project_id, work),
                daemon=True,
            )
            self._threads[project_id] = thread
            thread.start()

    def _run(self, project_id: UUID, work) -> None:
        try:
            work()
        except Exception as error:  # surfaced on the page, not swallowed
            logger.exception("Engagement %s failed.", project_id)
            self._errors[project_id] = str(error)


class ReviewApp:
    """
    Routing and request handling, independent of the HTTP server itself so it
    can be exercised directly in tests.
    """

    def __init__(self, service, projects, missions=None, runner=None) -> None:
        self._service = service
        self._projects = projects
        self._missions = missions
        self._runner = runner or EngagementRunner()

    # ------------------------------------------------------------- routing

    def get(self, path: str, query: dict) -> tuple[int, str]:
        parts = [p for p in path.strip("/").split("/") if p]

        try:
            if not parts:
                return 200, self._index()

            if parts[0] != "engagement" or len(parts) < 2:
                return 404, pages.error_page(f"Unknown path '{path}'.")

            project = self._projects.load(UUID(parts[1]))

            if len(parts) == 2:
                return 200, pages.engagement(
                    project,
                    busy=self._runner.busy(project.id),
                    error=self._runner.error(project.id),
                )

            if len(parts) >= 4 and parts[2] == "deliverable":
                return self._deliverable(project, parts, query)

            return 404, pages.error_page(f"Unknown path '{path}'.")

        except (ValueError, KeyError, FileNotFoundError) as error:
            return 404, pages.error_page(str(error))

    def post(self, path: str, form: dict) -> tuple[int, str]:
        parts = [p for p in path.strip("/").split("/") if p]

        try:
            if len(parts) < 3 or parts[0] != "engagement":
                return 404, pages.error_page(f"Unknown path '{path}'.")

            project = self._projects.load(UUID(parts[1]))

            if parts[2] == "resume":
                return self._resume(project)

            if len(parts) == 5 and parts[2] == "deliverable" and parts[4] == "review":
                return self._review(project, parts[3], form)

            return 404, pages.error_page(f"Unknown path '{path}'.")

        except (ValueError, KeyError, FileNotFoundError) as error:
            return 400, pages.error_page(str(error), code=400)

    # ------------------------------------------------------------ handlers

    def _index(self) -> str:
        projects = []
        unreadable = []

        for project_id in self._projects.list_ids():
            try:
                projects.append(self._projects.load(project_id))
            except Exception as error:
                # Never silently drop an engagement: a reviewer would have no
                # way to tell the difference between "not there" and "broken".
                logger.warning("Unreadable engagement %s: %s", project_id, error)
                unreadable.append((project_id, str(error)))

        missions = self._missions.list() if self._missions else []

        return pages.index(projects, missions, unreadable)

    def _deliverable(self, project, parts, query) -> tuple[int, str]:
        key = parts[3]

        try:
            deliverable = project.deliverable(key)
        except UnknownDeliverableError as error:
            return 404, pages.error_page(str(error))

        if len(parts) == 5 and parts[4] == "diff":
            versions = [v.version for v in deliverable.versions]

            if len(versions) < 2:
                return 404, pages.error_page(
                    "This deliverable has only one version; there is nothing "
                    "to compare."
                )

            after = int(query.get("to", [versions[-1]])[0])
            before = int(query.get("from", [max(v for v in versions if v < after)])[0])

            return 200, pages.diff_view(project, deliverable, before, after)

        version = query.get("version")

        return 200, pages.deliverable_view(
            project,
            deliverable,
            int(version[0]) if version else None,
        )

    def _review(self, project, key: str, form: dict) -> tuple[int, str]:
        decision = form.get("decision", [""])[0]
        note = form.get("note", [""])[0].strip() or None

        if decision == "approve":
            project.approve(key, summary=note)
        elif decision == "reject":
            if not note:
                return 400, pages.error_page(
                    "Feedback is required when sending a deliverable back — "
                    "it is passed to the model as the rework brief.",
                    code=400,
                )
            project.request_changes(key, summary=note)
        else:
            return 400, pages.error_page("Unknown review decision.", code=400)

        self._projects.save(project)

        return 303, f"/engagement/{project.id}"

    def _resume(self, project) -> tuple[int, str]:
        self._runner.start(
            project.id,
            lambda: self._service.resume(self._projects.load(project.id)),
        )

        return 303, f"/engagement/{project.id}"


def build_handler(app: ReviewApp):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Hyperium"

        def do_GET(self):  # noqa: N802 - required by BaseHTTPRequestHandler
            parsed = urlparse(self.path)
            status, body = app.get(parsed.path, parse_qs(parsed.query))
            self._respond(status, body)

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length).decode("utf-8") if length else ""

            parsed = urlparse(self.path)
            status, body = app.post(parsed.path, parse_qs(raw))
            self._respond(status, body)

        def _respond(self, status: int, body: str) -> None:
            if status == 303:
                self.send_response(303)
                self.send_header("Location", body)
                self.end_headers()
                return

            payload = body.encode("utf-8")

            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'",
            )
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt, *args):
            logger.debug("web: " + fmt, *args)

    return Handler


def serve(app: ReviewApp, host: str = "127.0.0.1", port: int = 8765):
    httpd = ThreadingHTTPServer((host, port), build_handler(app))

    return httpd
