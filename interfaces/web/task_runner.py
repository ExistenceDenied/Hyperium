"""
Running direct-task agents from the web, with web-mediated approval.

Each task has its own folder under the workspace — its working directory. Files
a person uploads for the task and files the agent produces both live there, so a
task's inputs and outputs stay with the task. An agent run happens on a
background thread and may pause partway to ask permission to act.
"""

from __future__ import annotations

import logging
import threading
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

from application.agent.task_service import deliverables_from
from core.agents.agent_result import AgentResult, AgentStep
from core.agents.approval import ActionRequest, ApprovalDecision
from core.agents.task_record import TaskRecord
from core.interfaces.approver import Approver

logger = logging.getLogger(__name__)


class WebApprover(Approver):
    """
    Approves actions through the browser.

    `review` runs on the task's background thread and blocks until a person
    answers in the web UI; `resolve` runs on a request thread and unblocks it.
    Only one action is ever in flight — the agent loop is sequential — so a
    single pending slot is enough.
    """

    def __init__(self) -> None:
        self._pending: ActionRequest | None = None
        self._decision: ApprovalDecision | None = None
        self._event = threading.Event()
        self._lock = threading.Lock()

    def review(self, request: ActionRequest) -> ApprovalDecision:
        with self._lock:
            self._pending = request
            self._decision = None
            self._event.clear()

        self._event.wait()

        with self._lock:
            self._pending = None
            return self._decision or ApprovalDecision.deny("no decision recorded")

    def pending(self) -> ActionRequest | None:
        with self._lock:
            return self._pending

    def resolve(self, approved: bool, reason: str | None = None) -> None:
        with self._lock:
            self._decision = ApprovalDecision(approved=approved, reason=reason)
        self._event.set()


@dataclass
class _Run:
    id: UUID
    prompt: str
    approver: WebApprover
    result: AgentResult | None = None
    error: str | None = None
    artifacts: list[str] = field(default_factory=list)


@dataclass
class TaskView:
    """A task's state for the page, whether it is live or read from the log."""

    id: UUID
    prompt: str
    status: str
    active: bool
    output: str = ""
    steps: list[AgentStep] = field(default_factory=list)
    error: str | None = None
    pending: ActionRequest | None = None
    files: list[tuple[str, int]] = field(default_factory=list)


class WebTaskRunner:
    """
    Starts direct-task runs, tracks the live ones, and reads finished ones back.

    Each run executes in its own folder under the workspace. Writes are always
    available to the agent, but every one is held at the approval gate, so the
    control is the person approving rather than a switch set beforehand.
    """

    def __init__(self, build_runner, repository, model, system, workspace) -> None:
        self._build_runner = build_runner
        self._repository = repository
        self._model = model
        self._system = system
        self._workspace = Path(workspace)
        self._runs: dict[UUID, _Run] = {}
        self._lock = threading.Lock()

    def folder(self, task_id: UUID) -> Path:
        return self._workspace / "tasks" / str(task_id)

    def files(self, task_id: UUID) -> list[tuple[str, int]]:
        directory = self.folder(task_id)
        if not directory.is_dir():
            return []
        return sorted(
            (path.name, path.stat().st_size)
            for path in directory.iterdir()
            if path.is_file()
        )

    def save_uploads(self, task_id: UUID, uploads) -> None:
        directory = self.folder(task_id)
        directory.mkdir(parents=True, exist_ok=True)
        for name, content in uploads:
            safe = Path(name).name  # drop any directory the browser sent
            if safe:
                (directory / safe).write_bytes(content)

    def start(self, prompt: str, uploads=None, task_id: UUID | None = None) -> UUID:
        task_id = task_id or uuid4()
        self.folder(task_id).mkdir(parents=True, exist_ok=True)

        if uploads:
            self.save_uploads(task_id, uploads)

        run = _Run(id=task_id, prompt=prompt, approver=WebApprover())

        with self._lock:
            self._runs[task_id] = run

        threading.Thread(target=self._execute, args=(run,), daemon=True).start()

        return task_id

    def approve(self, task_id: UUID, approved: bool, reason: str | None = None) -> None:
        run = self._runs.get(task_id)
        if run is not None:
            run.approver.resolve(approved, reason)

    def view(self, task_id: UUID) -> TaskView | None:
        files = self.files(task_id)
        run = self._runs.get(task_id)

        if run is not None:
            return self._live_view(run, files)

        try:
            record = self._repository.get(task_id)
        except Exception:
            return None

        result = record.result

        return TaskView(
            id=record.id,
            prompt=record.prompt,
            status=record.status if result else "pending",
            active=False,
            output=result.output if result else "",
            steps=list(result.steps) if result else [],
            files=files,
        )

    def index(self) -> list[TaskView]:
        with self._lock:
            ids = list(self._runs.keys())

        seen = set(ids)
        for record in self._repository.list():
            if record.id not in seen:
                ids.append(record.id)
                seen.add(record.id)

        views = [self.view(task_id) for task_id in ids]
        views = [view for view in views if view is not None]

        return sorted(views, key=lambda view: not view.active)

    def _live_view(self, run: _Run, files) -> TaskView:
        if run.error is not None:
            return TaskView(
                run.id, run.prompt, "failed", False, error=run.error, files=files
            )

        if run.result is not None:
            return TaskView(
                run.id,
                run.prompt,
                run.result.stop_reason.value,
                False,
                output=run.result.output,
                steps=list(run.result.steps),
                files=files,
            )

        pending = run.approver.pending()

        if pending is not None:
            return TaskView(
                run.id,
                run.prompt,
                "awaiting approval",
                True,
                pending=pending,
                files=files,
            )

        return TaskView(run.id, run.prompt, "running", True, files=files)

    def _execute(self, run: _Run) -> None:
        try:
            root = self.folder(run.id)

            with ExitStack() as stack:
                runner = self._build_runner(run.approver, stack, root)
                result = runner.run(run.prompt, system=self._system)

            run.artifacts = deliverables_from(result.steps, root)
            # Persist before flipping the view to done, so a reader that sees
            # "completed" can always load the saved record.
            self._repository.save(
                TaskRecord(
                    prompt=run.prompt,
                    id=run.id,
                    model=self._model,
                    result=result,
                    artifacts=run.artifacts,
                )
            )
            run.result = result
        except Exception as error:
            logger.exception("Web task %s failed.", run.id)
            run.error = str(error)
