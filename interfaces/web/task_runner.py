"""
Running direct-task agents from the web, with web-mediated approval.

An agent run is long and may pause partway to ask permission to act. Neither
fits a single request, so a run happens on a background thread and the page
reports its state — including the moment it is waiting for a human to approve
an action.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from uuid import UUID, uuid4

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
    allow_writes: bool
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
    artifacts: list[str] = field(default_factory=list)


class WebTaskRunner:
    """
    Starts direct-task runs, tracks the live ones, and reads finished ones back.

    `build_runner(approver, allow_writes)` yields a configured AgentRunner. The
    runner persists each completed run to the same task log the CLI writes, so
    history survives a restart while in-flight runs are held in memory.
    """

    def __init__(self, build_runner, repository, model, system, root=None) -> None:
        self._build_runner = build_runner
        self._repository = repository
        self._model = model
        self._system = system
        self._root = root
        self._runs: dict[UUID, _Run] = {}
        self._lock = threading.Lock()

    def start(self, prompt: str, allow_writes: bool) -> UUID:
        run = _Run(
            id=uuid4(),
            prompt=prompt,
            approver=WebApprover(),
            allow_writes=allow_writes,
        )

        with self._lock:
            self._runs[run.id] = run

        threading.Thread(target=self._execute, args=(run,), daemon=True).start()

        return run.id

    def approve(self, task_id: UUID, approved: bool, reason: str | None = None) -> None:
        run = self._runs.get(task_id)

        if run is not None:
            run.approver.resolve(approved, reason)

    def view(self, task_id: UUID) -> TaskView | None:
        run = self._runs.get(task_id)

        if run is not None:
            return self._live_view(run)

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
            artifacts=list(record.artifacts),
        )

    def index(self) -> list[TaskView]:
        """Every task, live runs first, then the log — newest history first."""
        with self._lock:
            live = [self._live_view(run) for run in self._runs.values()]

        views = sorted(live, key=lambda view: view.active, reverse=True)
        seen = {view.id for view in views}

        for record in self._repository.list():
            if record.id not in seen:
                view = self.view(record.id)
                if view is not None:
                    views.append(view)

        return views

    def _live_view(self, run: _Run) -> TaskView:
        if run.error is not None:
            return TaskView(run.id, run.prompt, "failed", False, error=run.error)

        if run.result is not None:
            return TaskView(
                run.id,
                run.prompt,
                run.result.stop_reason.value,
                False,
                output=run.result.output,
                steps=list(run.result.steps),
                artifacts=list(run.artifacts),
            )

        pending = run.approver.pending()

        if pending is not None:
            return TaskView(
                run.id, run.prompt, "awaiting approval", True, pending=pending
            )

        return TaskView(run.id, run.prompt, "running", True)

    def _execute(self, run: _Run) -> None:
        from contextlib import ExitStack

        try:
            # The stack keeps any connector subprocesses alive for the whole
            # run and closes them when it finishes.
            with ExitStack() as stack:
                runner = self._build_runner(run.approver, run.allow_writes, stack)
                result = runner.run(run.prompt, system=self._system)

            from application.agent.task_service import deliverables_from

            run.result = result
            run.artifacts = deliverables_from(result.steps, self._root)
            self._repository.save(
                TaskRecord(
                    prompt=run.prompt,
                    id=run.id,
                    model=self._model,
                    result=result,
                    artifacts=run.artifacts,
                )
            )
        except Exception as error:
            logger.exception("Web task %s failed.", run.id)
            run.error = str(error)
