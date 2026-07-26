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
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from application.agent.task_service import deliverables_from
from core.agents.agent_result import AgentResult, AgentStep
from core.agents.approval import ActionRequest, ApprovalDecision
from core.agents.task_record import Exchange, Note, TaskRecord
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

    def __init__(self, on_pending=None) -> None:
        self._pending: ActionRequest | None = None
        self._decision: ApprovalDecision | None = None
        self._event = threading.Event()
        self._lock = threading.Lock()
        # Called when an action starts waiting for a person — so it can be
        # surfaced as an alert rather than sitting unseen behind the gate.
        self._on_pending = on_pending or (lambda request: None)

    def review(self, request: ActionRequest) -> ApprovalDecision:
        with self._lock:
            self._pending = request
            self._decision = None
            self._event.clear()

        try:
            self._on_pending(request)
        except Exception:  # a notification must never block the gate
            logger.exception("Approval notification failed.")

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
    #: Earlier finished turns, when this run is a reply continuing a thread.
    history: list[Exchange] = field(default_factory=list)
    #: Where the task came from, so a deliverable can be fed back there.
    origin: dict | None = None


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
    history: list[Exchange] = field(default_factory=list)


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
        reviewer=None,
        max_concurrent=1,
        notify=None,
        deliver=None,
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
        # reviewer(prompt, output) -> [improvement task descriptions].
        self._reviewer = reviewer
        self._max_concurrent = max_concurrent
        # notify(kind, text, link) -> record an alert for the person.
        self._notify = notify or (lambda kind, text, link="": None)
        # deliver(origin, folder) -> feed a finished deliverable back to where the
        # task came from (e.g. reply to the email that spawned it, attaching it).
        self._deliver = deliver or (lambda origin, folder: None)
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
        history=None,
        origin=None,
    ) -> UUID:
        task_id = task_id or uuid4()
        self.folder(task_id).mkdir(parents=True, exist_ok=True)

        if uploads:
            self.save_uploads(task_id, uploads)

        def on_pending(request):
            self._notify(
                "approval",
                f"A task needs your approval: {request.preview}",
                f"/tasks/{task_id}",
            )

        run = _Run(
            id=task_id,
            prompt=prompt,
            approver=WebApprover(on_pending=on_pending),
            priority=priority,
            technique=technique,
            methodology=methodology,
            history=list(history or []),
            origin=origin,
        )

        with self._lock:
            self._runs[task_id] = run

        threading.Thread(target=self._execute, args=(run,), daemon=True).start()

        return task_id

    def queue(
        self,
        prompt: str,
        uploads=None,
        priority: str = "medium",
        technique: str = "",
        methodology: str = "",
        origin=None,
    ) -> UUID:
        """Add a task to the queue for the worker to launch, rather than now."""
        task_id = uuid4()
        self.folder(task_id).mkdir(parents=True, exist_ok=True)
        if uploads:
            self.save_uploads(task_id, uploads)

        self._repository.save(
            TaskRecord(
                id=task_id,
                prompt=prompt,
                model=self._model,
                priority=priority,
                technique=technique,
                methodology=methodology,
                queued=True,
                origin=origin,
            )
        )
        return task_id

    def pump(self) -> None:
        """Launch queued tasks while there is capacity — the worker's tick."""
        with self._lock:
            running = sum(
                1
                for run in self._runs.values()
                if run.result is None and run.error is None
            )

        if running >= self._max_concurrent:
            return

        order = {"high": 0, "medium": 1, "low": 2}
        queued = sorted(
            (
                record
                for record in self._repository.list()
                if record.queued and record.id not in self._runs
            ),
            key=lambda record: (order.get(record.priority, 1), record.created_at),
        )

        for record in queued:
            if running >= self._max_concurrent:
                break
            self.start(
                record.prompt,
                task_id=record.id,
                priority=record.priority,
                technique=record.technique,
                methodology=record.methodology,
            )
            running += 1

    def start_worker(self, interval: float = 5.0) -> None:
        """Continuously check the queue and launch tasks when capacity allows."""

        def loop():
            while True:
                try:
                    self.pump()
                except Exception:
                    logger.exception("Task queue worker failed a pass.")
                time.sleep(interval)

        threading.Thread(target=loop, daemon=True).start()

    def suggest_improvements(self, task_id: UUID) -> None:
        """Have a reviewer read a finished task and queue improvement tasks."""
        if self._reviewer is None:
            return

        def work():
            view = self.view(task_id)
            if view is None or not view.output:
                return
            try:
                suggestions = self._reviewer(view.prompt, view.output)
            except Exception:
                logger.exception("Improvement reviewer failed for %s.", task_id)
                return
            for text in suggestions:
                if text.strip():
                    self.queue(text.strip(), priority="low")

        threading.Thread(target=work, daemon=True).start()

    def follow_up(self, task_id: UUID, message: str) -> None:
        """
        Reply to a finished task, continuing it as a thread.

        The turn that just finished is pushed into the history, and the reply
        runs in the same folder — so the agent keeps the files it already made
        and the thread behind it, rather than starting from nothing.
        """
        try:
            record = self._repository.get(task_id)
        except Exception:
            record = None
        if record is None:
            return

        history = list(record.history)
        if record.result is not None:
            history.append(Exchange(record.prompt, record.result.output))

        self.start(
            message,
            task_id=task_id,
            priority=record.priority,
            technique=record.technique,
            methodology=record.methodology,
            history=history,
        )

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
                status=record.status,
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
            view.history = list(record.history)

        # A reply in flight carries the accumulated thread on the run, before
        # the record is rewritten — show that so the page is right mid-run.
        if run is not None and run.history:
            view.history = list(run.history)

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

        if run.history:
            thread = [
                "This task is a conversation. Here is what came before — continue "
                "it, staying consistent with what you already produced and editing "
                "the same files rather than starting over:"
            ]
            for turn in run.history:
                thread.append(f"\nAsked: {turn.prompt}\nYou produced:\n{turn.output}")
            preamble.append("\n".join(thread))

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
            # A reply carries the thread on the run; a plain re-run keeps
            # whatever thread the saved record already had.
            try:
                prior = self._repository.get(run.id)
            except Exception:
                prior = None
            existing = prior.notes if prior else []
            history = run.history or (prior.history if prior else [])
            origin = run.origin or (prior.origin if prior else None)
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
                    history=list(history),
                    origin=origin,
                )
            )
            run.result = result
            self._notify(
                "task",
                f"Task finished: {run.prompt[:70]}",
                f"/tasks/{run.id}",
            )
            # Feed the deliverable back to where the task came from (e.g. reply
            # to the originating email, attaching what was produced).
            if origin:
                try:
                    self._deliver(origin, self.folder(run.id))
                except Exception:
                    logger.exception("Delivering task %s to its origin failed.", run.id)
        except Exception as error:
            logger.exception("Web task %s failed.", run.id)
            run.error = str(error)
            self._notify(
                "error",
                f"Task failed: {run.prompt[:70]}",
                f"/tasks/{run.id}",
            )
