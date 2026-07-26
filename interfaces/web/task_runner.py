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
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from application.agent.task_service import deliverables_from
from core.agents.agent_result import AgentResult, AgentStep
from core.agents.approval import ActionRequest, ApprovalDecision
from core.agents.task_record import Note, TaskRecord
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
    priority: str = "medium"
    technique: str = ""
    methodology: str = ""
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
    priority: str = "medium"
    duration: float | None = None
    notes: list[Note] = field(default_factory=list)
    technique: str = ""
    methodology: str = ""


class WebTaskRunner:
    """
    Starts direct-task runs, tracks the live ones, and reads finished ones back.

    Each run executes in its own folder under the workspace. Writes are always
    available to the agent, but every one is held at the approval gate, so the
    control is the person approving rather than a switch set beforehand.
    """

    def __init__(
        self,
        build_runner,
        repository,
        model,
        system,
        workspace,
        approach=None,
        context=None,
    ) -> None:
        self._build_runner = build_runner
        self._repository = repository
        self._model = model
        self._system = system
        self._workspace = Path(workspace)
        # approach(technique_key, methodology_key) -> guidance text to prepend.
        self._approach = approach or (lambda technique, methodology: "")
        # context() -> the business memory prepended to every task.
        self._context = context or (lambda: "")
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

    def start(
        self,
        prompt: str,
        uploads=None,
        task_id: UUID | None = None,
        priority: str = "medium",
        technique: str = "",
        methodology: str = "",
    ) -> UUID:
        task_id = task_id or uuid4()
        self.folder(task_id).mkdir(parents=True, exist_ok=True)

        if uploads:
            self.save_uploads(task_id, uploads)

        run = _Run(
            id=task_id,
            prompt=prompt,
            approver=WebApprover(),
            priority=priority,
            technique=technique,
            methodology=methodology,
        )

        with self._lock:
            self._runs[task_id] = run

        threading.Thread(target=self._execute, args=(run,), daemon=True).start()

        return task_id

    def approve(self, task_id: UUID, approved: bool, reason: str | None = None) -> None:
        run = self._runs.get(task_id)
        if run is not None:
            run.approver.resolve(approved, reason)

    def add_note(self, task_id: UUID, text: str) -> None:
        try:
            record = self._repository.get(task_id)
        except Exception:
            run = self._runs.get(task_id)
            record = TaskRecord(
                id=task_id,
                prompt=run.prompt if run else "",
                priority=run.priority if run else "medium",
            )

        record.notes.append(Note(text=text))
        self._repository.save(record)

    def view(self, task_id: UUID) -> TaskView | None:
        files = self.files(task_id)
        run = self._runs.get(task_id)

        try:
            record = self._repository.get(task_id)
        except Exception:
            record = None

        if run is None and record is None:
            return None

        if run is not None:
            view = self._live_view(run, files)
            view.priority = run.priority
            view.technique = run.technique
            view.methodology = run.methodology
        else:
            result = record.result
            view = TaskView(
                id=record.id,
                prompt=record.prompt,
                status=record.status if result else "pending",
                active=False,
                output=result.output if result else "",
                steps=list(result.steps) if result else [],
                files=files,
            )

        # Ticket metadata — priority, notes, how long it took — lives on the
        # persisted record, which outlives the in-memory run.
        if record is not None:
            view.priority = record.priority
            view.notes = list(record.notes)
            view.duration = record.duration_seconds
            view.technique = record.technique
            view.methodology = record.methodology

        return view

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

    def _prompt(self, run: _Run) -> str:
        """
        The task, prefixed with the chosen approach and the files it can use.

        A technique or methodology adds its guidance and template up front so the
        work follows it; naming the attached files means a weaker model reads
        them rather than asking "what's the file path?".
        """
        preamble = []

        memory = self._context()
        if memory:
            preamble.append(memory)

        approach = self._approach(run.technique, run.methodology)
        if approach:
            preamble.append(approach)

        available = [name for name, _ in self.files(run.id)]
        if available:
            preamble.append(
                "Files provided for this task are in your working directory. "
                "Read them by name with read_excel or read_file — do not ask "
                "for a path. Available files: " + ", ".join(available) + "."
            )

        if not preamble:
            return run.prompt

        return "\n\n".join(preamble) + "\n\nTask: " + run.prompt

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
                result = runner.run(self._prompt(run), system=self._system)

            run.artifacts = deliverables_from(result.steps, root)
            # Keep notes added while the task ran, and stamp the finish time.
            try:
                existing = self._repository.get(run.id).notes
            except Exception:
                existing = []
            # Persist before flipping the view to done, so a reader that sees
            # "completed" can always load the saved record.
            self._repository.save(
                TaskRecord(
                    prompt=run.prompt,
                    id=run.id,
                    model=self._model,
                    result=result,
                    artifacts=run.artifacts,
                    priority=run.priority,
                    technique=run.technique,
                    methodology=run.methodology,
                    completed_at=datetime.now(timezone.utc),
                    notes=existing,
                )
            )
            run.result = result
        except Exception as error:
            logger.exception("Web task %s failed.", run.id)
            run.error = str(error)
