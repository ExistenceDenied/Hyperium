"""
Command line interface for running and reviewing engagements.

This is the human-in-the-loop seam. Hyperium executes until it produces a
deliverable, then stops and waits here for a person to approve or reject.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from uuid import UUID

from application.missions.mission_backlog_service import MissionBacklogService
from application.project.project_builder import ProjectBuilder
from config.settings import Settings
from core.capabilities.capability_catalog import CapabilityCatalog
from core.capabilities.proficiency_level import ProficiencyLevel
from core.missions.mission import MissionStateError
from core.missions.mission_priority import MissionPriority
from core.missions.mission_status import MissionStatus
from core.project.project import Project
from core.resources.ai_resource import AIResource
from infrastructure.artifacts.file_artifact_store import FileArtifactStore
from infrastructure.llm.ollama_provider import OllamaProvider
from infrastructure.llm.resilient_provider import ResilientProvider
from infrastructure.methodologies.json_methodology_repository import (
    BUILTIN_ROOT,
    JsonMethodologyRepository,
)
from infrastructure.observability.logging_setup import configure_logging
from infrastructure.persistence.mission_repository import MissionRepository
from infrastructure.persistence.project_repository import ProjectRepository


def build_activity_executor(settings: Settings):
    """
    The agentic executor for engagements: activities run as tool-using agents.

    The tools are read-only and scoped to the workspace, and side effects are
    denied — an engagement may run unattended (from the web UI), so it must not
    act on anything without a person present. The agent's gain here is grounding
    deliverable content in real files rather than only prior knowledge.
    """
    from application.agent.agent_runner import AgentRunner
    from application.agent.approval_policies import AutoDenyApprover
    from application.execution.agent_activity_executor import AgentActivityExecutor
    from infrastructure.llm.ollama_agent_provider import OllamaAgentProvider
    from infrastructure.memory import MemoryStore
    from infrastructure.tools import read_only_tools

    provider = OllamaAgentProvider(
        model=settings.model,
        timeout_seconds=settings.llm_timeout_seconds,
        temperature=settings.temperature,
    )

    context = MemoryStore(settings.state_directory / "memory.json").as_context()

    return AgentActivityExecutor(
        AgentRunner(
            provider,
            read_only_tools(settings.workspace),
            approver=AutoDenyApprover(),
        ),
        context=context,
    )


def build_llm(
    settings: Settings, model: str | None = None, json_mode: bool = False
) -> ResilientProvider:
    return ResilientProvider(
        OllamaProvider(
            model=model or settings.model,
            timeout_seconds=settings.llm_timeout_seconds,
            temperature=settings.temperature,
            response_format="json" if json_mode else None,
            think=False if json_mode else None,
        ),
        attempts=settings.llm_attempts,
        backoff_seconds=settings.llm_backoff_seconds,
    )


def run_autonomously(args, settings: Settings, project):
    """Review and iterate an engagement to completion with no human in the loop."""
    from application.project.autonomous_runner import AutonomousRunner
    from application.review.quality_reviewer import QualityReviewer

    service, _ = build_context(settings)
    reviewer = QualityReviewer(
        build_llm(settings, settings.review_model or None, json_mode=True)
    )

    outcome = AutonomousRunner(
        service, reviewer, max_revisions=args.max_revisions
    ).run(project)

    print("\nAutonomous review log:")
    for decision in outcome.decisions:
        note = decision.feedback.replace("\n", " ")[:80]
        print(f"  [{decision.decision:<11}] {decision.deliverable}: {note}")

    if outcome.halted_on:
        print(
            f"\nHalted: '{outcome.halted_on}' did not pass review within "
            f"{args.max_revisions} revisions. It is left for you to decide.",
            file=sys.stderr,
        )

    return outcome.project


def build_context(settings: Settings):
    provider = build_llm(settings)

    methodologies = build_methodologies(settings)

    repository = ProjectRepository(settings.state_directory)
    store = FileArtifactStore(settings.workspace)

    from infrastructure.templates import TemplateLibrary

    service = ProjectBuilder.build(
        provider,
        store,
        repository=repository,
        methodologies=methodologies,
        default_methodology=settings.default_methodology,
        activity_executor=build_activity_executor(settings),
        templates=TemplateLibrary(),
    )

    return service, repository


def build_methodologies(settings: Settings) -> JsonMethodologyRepository:
    roots = [BUILTIN_ROOT]

    if settings.methodology_directory:
        roots.append(settings.methodology_directory)

    return JsonMethodologyRepository(roots)


def build_backlog(settings: Settings) -> MissionBacklogService:
    service, _ = build_context(settings)

    return MissionBacklogService(
        MissionRepository(settings.state_directory / "missions"),
        project_service=service,
    )


def default_resource(settings: Settings) -> AIResource:
    resource = AIResource(
        name=f"Ollama ({settings.model})",
        provider="Ollama",
        model=settings.model,
    )

    for key in CapabilityCatalog.keys():
        resource.add_capability(
            CapabilityCatalog.get(key),
            ProficiencyLevel.ADVANCED,
        )

    return resource


def group_by_stage(project: Project) -> dict:
    """Deliverables grouped by stage, in methodology order."""
    grouped: dict = {}

    for deliverable in project.deliverables:
        grouped.setdefault(deliverable.stage, []).append(deliverable)

    return grouped


def report(project: Project) -> None:
    result = project.execution_result

    print(f"\nEngagement {project.id}")
    print(f"Mission:    {project.mission.title}")
    print(f"Status:     {result.status.value}")
    print(f"Activities: {result.activities_executed} executed this pass")

    plan = project.execution_plan

    if plan is not None and plan.methodology_key:
        print(f"Methodology: {plan.methodology_key}")

    print("\nDeliverables:")

    for stage_key, deliverables in group_by_stage(project).items():
        gate = plan.gate_result(stage_key) if plan and stage_key else None

        if stage_key:
            mark = "open" if gate is None or gate.passed else "gated"
            print(f"  -- {stage_key}  [{mark}]")

            # Evaluated now, not read from the last run's log: the stored log
            # goes stale the moment a deliverable is approved.
            if gate is not None and not gate.passed:
                for failure in gate.failures:
                    print(f"       ! {failure}")

        for deliverable in deliverables:
            version = deliverable.latest_version()
            label = (
                f"v{version.version} ({version.filename})"
                if version
                else "no content"
            )
            print(
                f"  [{deliverable.status.value:<18}] "
                f"{deliverable.key:<28} {label}"
            )

    if result.messages:
        print("\nLog from the last run:")
        for message in result.messages:
            print(f"  - {message}")

    pending = [item.key for item in project.awaiting_approval]

    if pending:
        print("\nAwaiting your review:")
        for key in pending:
            print(f"  hyperium approve {project.id} {key}")
            print(f"  hyperium reject  {project.id} {key} --note '...'")


def show_mission(mission, verbose: bool = False) -> None:
    flag = "" if mission.is_complete else "  (incomplete - needs a success criterion)"

    print(f"\n{mission.title}")
    print(f"  id:        {mission.id}")
    print(f"  status:    {mission.status.value}{flag}")
    print(f"  priority:  {mission.priority.name}")
    print(f"  objective: {mission.objective.description}")

    if mission.project_id:
        print(f"  engagement: {mission.project_id}")

    if verbose:
        for label, items in (
            ("success criteria", [c.description for c in mission.success_criteria]),
            (
                "constraints",
                [f"[{c.type.name}] {c.description}" for c in mission.constraints],
            ),
            (
                "stakeholders",
                [f"{s.name} ({s.role})" for s in mission.stakeholders],
            ),
        ):
            if items:
                print(f"  {label}:")
                for item in items:
                    print(f"    - {item}")


def command_methodology_list(args, settings: Settings) -> int:
    methodologies = build_methodologies(settings).all()

    print(f"{'KEY':<24} {'STAGES':<8} {'ACTIVITIES':<12} NAME")

    for item in methodologies:
        print(
            f"{item.key:<24} {len(item.stages):<8} "
            f"{len(item.activities):<12} {item.name}"
        )

    print(f"\nDefault: {settings.default_methodology}")

    return 0


def command_methodology_show(args, settings: Settings) -> int:
    repository = build_methodologies(settings)
    item = repository.get(args.key)

    print(f"\n{item.name}  ({item.key} v{item.version})")
    print(f"  {item.description}")

    if item.principles:
        print("\n  Principles:")
        for principle in item.principles:
            print(f"    - {principle}")

    for stage in item.stages:
        after = (
            f"  (after {', '.join(stage.depends_on)})" if stage.depends_on else ""
        )
        print(f"\n  ── Stage: {stage.name}{after}")

        if stage.quality_gate:
            gate = stage.quality_gate
            checks = []
            if gate.require_approval:
                checks.append("human approval")
            if gate.minimum_words:
                checks.append(f"min {gate.minimum_words} words")
            if gate.required_sections:
                checks.append(f"sections {', '.join(gate.required_sections)}")
            print(f"     gate: {'; '.join(checks) or 'none'}")

        for deliverable in stage.deliverables:
            print(f"     * {deliverable.name}  [{deliverable.key}]")

            for activity in deliverable.activities:
                technique = (
                    f"  via {activity.technique}" if activity.technique else ""
                )
                needs = ", ".join(activity.capabilities)
                print(f"         - {activity.name}  ({needs}){technique}")

    return 0


def command_methodology_techniques(args, settings: Settings) -> int:
    for technique in build_methodologies(settings).techniques():
        applies = ", ".join(sorted(technique.capabilities)) or "any capability"
        print(f"{technique.key:<28} {technique.name}  [{applies}]")

    return 0


def command_mission_add(args, settings: Settings) -> int:
    if args.methodology:
        # Fail here rather than at launch, when the run is already underway.
        build_methodologies(settings).get(args.methodology)

    mission = build_backlog(settings).create(
        title=args.title,
        objective=args.objective,
        priority=MissionPriority.parse(args.priority),
        criteria=args.criterion,
        constraints=args.constraint,
        stakeholders=args.stakeholder,
        methodology=args.methodology,
    )

    show_mission(mission, verbose=True)
    print(f"\nLaunch it with: hyperium launch {mission.id}")

    return 0


def command_mission_list(args, settings: Settings) -> int:
    status = MissionStatus(args.status.upper()) if args.status else None

    missions = build_backlog(settings).list(
        status=status,
        include_archived=args.all,
    )

    if not missions:
        print("The backlog is empty. Add one with: hyperium mission add ...")
        return 0

    print(f"{'PRIORITY':<10} {'STATUS':<10} {'ID':<38} TITLE")

    for mission in missions:
        print(
            f"{mission.priority.name:<10} {mission.status.value:<10} "
            f"{str(mission.id):<38} {mission.title}"
        )

    return 0


def command_mission_show(args, settings: Settings) -> int:
    show_mission(build_backlog(settings).get(UUID(args.mission_id)), verbose=True)

    return 0


def command_mission_edit(args, settings: Settings) -> int:
    backlog = build_backlog(settings)
    mission_id = UUID(args.mission_id)

    mission = backlog.update(
        mission_id,
        title=args.title,
        objective=args.objective,
        priority=(
            MissionPriority.parse(args.priority) if args.priority else None
        ),
        add_criteria=args.add_criterion,
        clear_criteria=args.clear_criteria,
        add_constraints=args.add_constraint,
        clear_constraints=args.clear_constraints,
    )

    if args.ready:
        mission = backlog.mark_ready(mission_id)

    if args.archive:
        mission = backlog.archive(mission_id)

    if args.restore:
        mission = backlog.restore(mission_id)

    show_mission(mission, verbose=True)

    return 0


def command_mission_delete(args, settings: Settings) -> int:
    mission = build_backlog(settings).delete(
        UUID(args.mission_id),
        force=args.force,
    )

    print(f"Deleted mission '{mission.title}'.")

    return 0


def command_launch(args, settings: Settings) -> int:
    project = build_backlog(settings).launch(
        UUID(args.mission_id),
        resources=[default_resource(settings)],
    )

    if getattr(args, "autonomous", False):
        project = run_autonomously(args, settings, project)

    report(project)

    return 0


def command_run(args, settings: Settings) -> int:
    """
    Shortcut: add a mission to the backlog and launch it immediately.

    Everything still lands in the backlog, so an ad-hoc run is not a second
    way of creating missions — just a faster path through the same one.
    """
    backlog = build_backlog(settings)

    criteria = args.criterion or [f"{args.title} is delivered and approved."]

    mission = backlog.create(
        title=args.title,
        objective=args.objective,
        priority=MissionPriority.parse(args.priority),
        criteria=criteria,
        methodology=args.methodology,
    )

    project = backlog.launch(mission.id, resources=[default_resource(settings)])

    if getattr(args, "autonomous", False):
        project = run_autonomously(args, settings, project)

    report(project)

    return 0


AGENT_SYSTEM = (
    "You are Hyperium, an autonomous assistant that completes tasks on the "
    "user's behalf using the tools available to you. Gather facts with your "
    "tools before answering — never guess at a file's contents, a page's text "
    "or a system's state. Files provided for the task are in your working "
    "directory: read them by name with read_file or read_excel, and use "
    "list_directory to see what is there — never ask the user for a file path. "
    "Some tools change things and will ask the user for approval first; if one "
    "is declined, find another way or say what you need. When you have enough "
    "information, act, then report the result clearly. Do not describe what you "
    "would do; do it."
)


def agent_tools(args, stack):
    """
    Assemble the toolset for a run, keeping any MCP servers open in ``stack``.

    Local file tools first, then every tool advertised by the MCP servers in
    the config. MCP servers are subprocesses, so they are entered into the
    caller's ExitStack and closed when it unwinds.
    """
    from infrastructure.tools import read_only_tools, writable_tools

    root = Path(args.root).resolve()
    tools = writable_tools(root) if args.allow_writes else read_only_tools(root)

    if getattr(args, "mcp", None):
        from infrastructure.mcp.config import load_mcp_config
        from infrastructure.mcp.mcp_client import McpClient
        from infrastructure.mcp.mcp_toolset import connect_mcp_tools

        for _name, spec in load_mcp_config(Path(args.mcp)).items():
            client = stack.enter_context(
                McpClient(spec.command, spec.args, env=spec.env)
            )
            tools.extend(connect_mcp_tools(client))

    return tools


def run_agent_task(args, settings: Settings, prompt: str) -> int:
    """Assemble tools, run the agent on `prompt`, record the run, report it."""
    from contextlib import ExitStack

    from application.agent.agent_runner import AgentRunner
    from application.agent.approval_policies import AutoApproveApprover
    from application.agent.task_service import TaskService
    from core.agents.agent_result import StopReason
    from infrastructure.llm.ollama_agent_provider import OllamaAgentProvider
    from infrastructure.persistence.task_repository import TaskRepository
    from interfaces.approval import ConsoleApprover

    approver = AutoApproveApprover() if args.auto_approve else ConsoleApprover()

    with ExitStack() as stack:
        runner = AgentRunner(
            OllamaAgentProvider(
                model=settings.model,
                timeout_seconds=settings.llm_timeout_seconds,
                temperature=settings.temperature,
            ),
            agent_tools(args, stack),
            max_iterations=args.max_steps,
            approver=approver,
        )

        # Runs inside the stack: MCP servers must stay alive for the whole run.
        result = runner.run(prompt, system=AGENT_SYSTEM)

    record = None
    if not args.no_save:
        service = TaskService(TaskRepository(settings.state_directory / "tasks"))
        record = service.record(
            prompt=prompt,
            result=result,
            model=settings.model,
            root=Path(args.root).resolve(),
            priority=getattr(args, "priority", "medium"),
        )

    if args.verbose and result.steps:
        print("Steps:")
        for step in result.steps:
            preview = step.result.replace("\n", " ")[:100]
            print(f"  - {step.tool}({step.arguments}) -> {preview}")
        print()

    print(result.output)

    if record is not None and record.artifacts:
        print("\nDeliverables:")
        for path in record.artifacts:
            print(f"  {path}")

    if record is not None:
        print(f"\nSaved as task {record.id}", file=sys.stderr)

    if result.stop_reason is StopReason.MAX_ITERATIONS:
        print(
            "\n(Stopped: reached the step limit. Raise it with --max-steps.)",
            file=sys.stderr,
        )
        return 1

    return 0


def command_do(args, settings: Settings) -> int:
    """
    Hand the agent a task; it uses tools and reports the result.

    The direct-task path: no mission or methodology. Read-only file tools by
    default. --allow-writes adds filesystem writes; --mcp connects external
    tools (email, files, ...) from an MCP config. Every acting tool is held at
    the approval gate — asked interactively, or auto-approved for a trusted
    unattended run. Each run is recorded unless --no-save is given.
    """
    return run_agent_task(args, settings, args.task)


def command_task_list(args, settings: Settings) -> int:
    from infrastructure.persistence.task_repository import TaskRepository

    records = TaskRepository(settings.state_directory / "tasks").list()

    if not records:
        print('No saved tasks yet. Run one with: hyperium do "..."')
        return 0

    print(f"{'ID':<38} {'WHEN':<17} {'STATUS':<12} {'PRIORITY':<9} PROMPT")
    for record in records:
        when = record.created_at.strftime("%Y-%m-%d %H:%M")
        prompt = record.prompt.replace("\n", " ")[:44]
        print(
            f"{str(record.id):<38} {when:<17} {record.status:<12} "
            f"{record.priority:<9} {prompt}"
        )

    return 0


def command_task_show(args, settings: Settings) -> int:
    from infrastructure.persistence.task_repository import TaskRepository

    record = TaskRepository(settings.state_directory / "tasks").get(
        UUID(args.task_id)
    )

    print(f"Task {record.id}")
    print(f"  when:     {record.created_at.isoformat()}")
    print(f"  model:    {record.model}")
    print(f"  status:   {record.status}")
    print(f"  priority: {record.priority}")

    if record.duration_seconds is not None:
        print(f"  took:     {int(record.duration_seconds)}s")

    print(f"\nPrompt:\n  {record.prompt}")

    if record.notes:
        print("\nNotes:")
        for note in record.notes:
            print(f"  - {note.text}  ({note.at.strftime('%Y-%m-%d %H:%M')})")

    if record.artifacts:
        print("\nDeliverables:")
        for path in record.artifacts:
            print(f"  {path}")

    if record.result:
        if record.result.steps:
            print("\nSteps:")
            for step in record.result.steps:
                preview = step.result.replace("\n", " ")[:100]
                print(f"  - {step.tool}({step.arguments}) -> {preview}")

        print(f"\nResult:\n{record.result.output}")

    return 0


def command_task_rerun(args, settings: Settings) -> int:
    from infrastructure.persistence.task_repository import TaskRepository

    record = TaskRepository(settings.state_directory / "tasks").get(
        UUID(args.task_id)
    )

    print(f"Re-running task {record.id}.", file=sys.stderr)

    return run_agent_task(args, settings, record.prompt)


def command_tools(args, settings: Settings) -> int:
    """List the tools an agent would have, local and MCP, and which need
    approval."""
    from contextlib import ExitStack

    with ExitStack() as stack:
        tools = agent_tools(args, stack)

        print(f"{'TOOL':<22} {'APPROVAL':<10} DESCRIPTION")
        for tool in tools:
            gate = "required" if tool.requires_approval else "-"
            print(f"{tool.name:<22} {gate:<10} {tool.description}")

    return 0


def command_resume(args, settings: Settings) -> int:
    service, repository = build_context(settings)

    project = repository.load(UUID(args.project_id))
    report(service.resume(project))

    return 0


def command_review(args, settings: Settings, approve: bool) -> int:
    service, repository = build_context(settings)

    project = repository.load(UUID(args.project_id))

    if approve:
        service.approve(project, args.deliverable, note=args.note)
    else:
        service.request_changes(project, args.deliverable, note=args.note)

    verdict = "approved" if approve else "sent back for changes"
    print(f"Deliverable '{args.deliverable}' {verdict}.")

    if approve:
        print(f"Continue with: hyperium resume {project.id}")

    return 0


def command_submit(args, settings: Settings) -> int:
    service, repository = build_context(settings)

    if args.file:
        content = Path(args.file).read_text(encoding="utf-8")
    elif args.text:
        content = args.text
    else:
        raise ValueError("Provide the work with --file or --text.")

    project = repository.load(UUID(args.project_id))

    report(service.submit_work(project, args.activity, content))

    return 0


def build_web_task_runner(settings: Settings):
    """The browser's task runner: agent runs with web-mediated approval."""
    from application.agent.agent_runner import AgentRunner
    from infrastructure.connectors import ConnectionStore
    from infrastructure.llm.ollama_agent_provider import OllamaAgentProvider
    from infrastructure.mcp.mcp_client import McpClient
    from infrastructure.mcp.mcp_toolset import connect_mcp_tools
    from infrastructure.memory import MemoryStore
    from infrastructure.methodologies.technique_repository import TechniqueRepository
    from infrastructure.persistence.task_repository import TaskRepository
    from infrastructure.tools import writable_tools
    from interfaces.web.task_runner import WebTaskRunner

    connections = ConnectionStore(settings.state_directory / "connections.json")
    techniques = TechniqueRepository(BUILTIN_ROOT / "techniques")
    methodologies = build_methodologies(settings)
    memory = MemoryStore(settings.state_directory / "memory.json")

    def approach(technique_key, methodology_key):
        parts = []

        if technique_key:
            technique = techniques.get(technique_key)
            if technique:
                block = [f"Apply the '{technique.name}' technique to this task."]
                if technique.guidance:
                    block.append(technique.guidance)
                if technique.template:
                    block.append("The output must follow this template:")
                    block.append(technique.template)
                parts.append("\n".join(block))

        if methodology_key:
            found = next(
                (m for m in methodologies.all() if m.key == methodology_key), None
            )
            if found:
                block = [
                    f"Work in the style of the '{found.name}' methodology.",
                    found.description,
                ]
                if found.principles:
                    block.append("Its principles: " + " ".join(found.principles))
                parts.append("\n".join(block))

        return "\n\n".join(parts)

    def make_runner(approver, stack, root):
        provider = OllamaAgentProvider(
            model=settings.model,
            timeout_seconds=settings.llm_timeout_seconds,
            temperature=settings.temperature,
        )
        # Always writable, scoped to the task's own folder — every write is held
        # at the approval gate, so the person deciding is the control.
        tools = writable_tools(root)

        # Best-effort: a connector that cannot start (missing Node, not signed
        # in) is logged and skipped, never fails the task.
        for name, spec in connections.specs().items():
            try:
                client = stack.enter_context(
                    McpClient(spec.command, spec.args, env=spec.env)
                )
                tools.extend(connect_mcp_tools(client))
            except Exception as error:
                logging.getLogger(__name__).warning(
                    "Connector '%s' is unavailable: %s", name, error
                )

        return AgentRunner(provider, tools, approver=approver)

    return WebTaskRunner(
        make_runner,
        TaskRepository(settings.state_directory / "tasks"),
        model=settings.model,
        system=AGENT_SYSTEM,
        workspace=settings.workspace,
        approach=approach,
        context=memory.as_context,
    )


def command_serve(args, settings: Settings) -> int:
    from infrastructure.connectors import ConnectionStore
    from infrastructure.memory import MemoryStore
    from infrastructure.methodologies.technique_repository import TechniqueRepository
    from interfaces.web.server import ReviewApp, serve

    service, repository = build_context(settings)

    app = ReviewApp(
        service,
        repository,
        missions=build_backlog(settings),
        methodologies=build_methodologies(settings),
        resources=lambda: [default_resource(settings)],
        tasks=build_web_task_runner(settings),
        connections=ConnectionStore(settings.state_directory / "connections.json"),
        workspace=settings.workspace,
        techniques=TechniqueRepository(BUILTIN_ROOT / "techniques"),
        memory=MemoryStore(settings.state_directory / "memory.json"),
    )

    httpd = serve(app, host=args.host, port=args.port)

    if args.host not in ("127.0.0.1", "localhost"):
        print(
            f"Warning: serving on {args.host} exposes this engagement to the "
            "network. There is no authentication.",
            file=sys.stderr,
        )

    print(f"Hyperium review UI:  http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()

    return 0


def deliverable_formats(project, settings: Settings) -> dict:
    """Map each deliverable key to the file type its methodology declares."""
    plan = project.execution_plan
    key = plan.methodology_key if plan else None

    if not key:
        return {}

    try:
        methodology = build_methodologies(settings).get(key)
    except (KeyError, FileNotFoundError):
        return {}

    return {item.key: (item.format or "markdown") for item in methodology.deliverables}


def command_export(args, settings: Settings) -> int:
    """
    Export an engagement's deliverables as the file types clients receive.

    Each deliverable is written in the format its methodology declares — Word,
    PowerPoint or Markdown — into a folder, alongside a bundled HTML overview.
    If the office dependency is missing, those deliverables fall back to
    Markdown and the run says so rather than failing.
    """
    from interfaces import office
    from interfaces.pack import build_html_pack

    _, repository = build_context(settings)
    project = repository.load(UUID(args.project_id))
    formats = deliverable_formats(project, settings)

    out_dir = (
        Path(args.output) if args.output else settings.workspace / f"pack-{project.id}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    for deliverable in project.deliverables:
        version = deliverable.latest_version()
        if version is None:
            continue

        fmt = (
            args.format
            if args.format != "auto"
            else formats.get(deliverable.key, "docx")
        )
        base = out_dir / deliverable.key

        try:
            if fmt == "pptx":
                path = base.with_suffix(".pptx")
                path.write_bytes(office.to_pptx(deliverable.name, version.content))
            elif fmt == "docx":
                path = base.with_suffix(".docx")
                path.write_bytes(office.to_docx(deliverable.name, version.content))
            elif fmt == "eml":
                path = base.with_suffix(".eml")
                path.write_bytes(office.to_eml(deliverable.name, version.content))
            else:
                path = base.with_suffix(".md")
                path.write_text(version.content, encoding="utf-8")
        except office.OfficeUnavailable as error:
            path = base.with_suffix(".md")
            path.write_text(version.content, encoding="utf-8")
            print(f"  ({error} — wrote {deliverable.key}.md instead)", file=sys.stderr)

        written.append(path.name)

    (out_dir / "index.html").write_text(build_html_pack(project), encoding="utf-8")

    print(f"Wrote {len(written)} deliverables + index.html to {out_dir}")
    for name in written:
        print(f"  - {name}")

    return 0


def command_list(args, settings: Settings) -> int:
    _, repository = build_context(settings)

    ids = repository.list_ids()

    if not ids:
        print("No engagements found.")
        return 0

    for project_id in ids:
        project = repository.load(project_id)
        waiting = len(project.awaiting_approval)
        result = project.execution_result
        status = result.status.value if result else "-"

        print(
            f"{project_id}  {status:<18} {waiting} awaiting review  "
            f"{project.mission.title}"
        )

    return 0


def command_show(args, settings: Settings) -> int:
    _, repository = build_context(settings)

    project = repository.load(UUID(args.project_id))

    if args.deliverable:
        deliverable = project.deliverable(args.deliverable)
        version = deliverable.latest_version()

        if version is None:
            print(f"Deliverable '{args.deliverable}' has no content yet.")
            return 1

        print(version.content)
        return 0

    report(project)
    return 0


def _add_autonomous_args(parser: argparse.ArgumentParser) -> None:
    """Flags shared by `run` and `launch` for an unattended, self-reviewed run."""
    parser.add_argument(
        "--autonomous",
        action="store_true",
        help="Review and iterate each deliverable with no human in the loop.",
    )
    parser.add_argument(
        "--max-revisions",
        type=int,
        default=2,
        dest="max_revisions",
        help="Revisions the reviewer may request per deliverable before it stops.",
    )


def _add_agent_run_args(parser: argparse.ArgumentParser) -> None:
    """The execution flags shared by `do` and `task rerun`."""
    parser.add_argument(
        "--root",
        default=".",
        help="Directory the file tools are confined to (default: current).",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=12,
        dest="max_steps",
        help="Maximum tool-using steps before the run is cut short.",
    )
    parser.add_argument(
        "--allow-writes",
        action="store_true",
        dest="allow_writes",
        help="Let the agent change files. Each write is held for approval.",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        dest="auto_approve",
        help="Approve every action without asking. Unattended runs only.",
    )
    parser.add_argument(
        "--mcp",
        default=None,
        help="Path to an MCP config; connects its servers' tools to the agent.",
    )
    parser.add_argument(
        "--priority",
        default="medium",
        choices=["low", "medium", "high"],
        help="Task priority, recorded on the task.",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        dest="no_save",
        help="Do not record this run in the task log.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show each tool call before the answer.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hyperium",
        description="Run and review AI consultancy engagements.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    method = sub.add_parser("methodology", help="Inspect available methodologies.")
    methods = method.add_subparsers(dest="methodology_command", required=True)

    methods.add_parser("list", help="List methodologies.")

    method_show = methods.add_parser("show", help="Show one in full.")
    method_show.add_argument("key")

    methods.add_parser("techniques", help="List the technique library.")

    mission = sub.add_parser("mission", help="Manage the mission backlog.")
    backlog = mission.add_subparsers(dest="mission_command", required=True)

    add = backlog.add_parser("add", help="Add a mission to the backlog.")
    add.add_argument("title")
    add.add_argument("objective", help="What the mission must achieve.")
    add.add_argument("--priority", default="medium", help="low|medium|high|critical")
    add.add_argument(
        "--methodology",
        default=None,
        help="Methodology key. Overrides whatever the analysis recommends.",
    )
    add.add_argument("--criterion", action="append", help="Repeatable.")
    add.add_argument(
        "--constraint",
        action="append",
        help="'type:description', e.g. 'TIME:Must ship in Q3'. Repeatable.",
    )
    add.add_argument(
        "--stakeholder",
        action="append",
        help="'name:role'. Repeatable.",
    )

    listing = backlog.add_parser("list", help="Show the backlog.")
    listing.add_argument("--status", default=None, help="Filter by status.")
    listing.add_argument(
        "--all",
        action="store_true",
        help="Include archived missions.",
    )

    detail = backlog.add_parser("show", help="Show one mission in full.")
    detail.add_argument("mission_id")

    edit = backlog.add_parser("edit", help="Change a mission in the backlog.")
    edit.add_argument("mission_id")
    edit.add_argument("--title", default=None)
    edit.add_argument("--objective", default=None)
    edit.add_argument("--priority", default=None)
    edit.add_argument("--add-criterion", action="append", dest="add_criterion")
    edit.add_argument("--clear-criteria", action="store_true")
    edit.add_argument("--add-constraint", action="append", dest="add_constraint")
    edit.add_argument("--clear-constraints", action="store_true")
    edit.add_argument("--ready", action="store_true", help="Mark as READY.")
    edit.add_argument("--archive", action="store_true")
    edit.add_argument("--restore", action="store_true")

    remove = backlog.add_parser("delete", help="Remove a mission.")
    remove.add_argument("mission_id")
    remove.add_argument(
        "--force",
        action="store_true",
        help="Delete even if the mission has been launched.",
    )

    launch = sub.add_parser("launch", help="Run a mission from the backlog.")
    launch.add_argument("mission_id")
    _add_autonomous_args(launch)

    run = sub.add_parser(
        "run",
        help="Add a mission and launch it immediately.",
    )
    run.add_argument("title")
    run.add_argument("objective", help="What the mission must achieve.")
    run.add_argument("--priority", default="medium")
    run.add_argument("--methodology", default=None)
    run.add_argument(
        "--criterion",
        action="append",
        help="A success criterion. May be repeated.",
    )
    _add_autonomous_args(run)

    do = sub.add_parser(
        "do",
        help="Give the agent a task; it uses tools and reports the result.",
    )
    do.add_argument("task", help="The task, in plain language.")
    _add_agent_run_args(do)

    tools = sub.add_parser(
        "tools",
        help="List the tools an agent can use, and which need approval.",
    )
    tools.add_argument("--root", default=".")
    tools.add_argument("--allow-writes", action="store_true", dest="allow_writes")
    tools.add_argument("--mcp", default=None, help="Path to an MCP config.")

    task = sub.add_parser("task", help="Inspect and re-run saved agent tasks.")
    task_sub = task.add_subparsers(dest="task_command", required=True)
    task_sub.add_parser("list", help="List saved tasks, newest first.")
    task_show = task_sub.add_parser("show", help="Show one saved task in full.")
    task_show.add_argument("task_id")
    task_rerun = task_sub.add_parser("rerun", help="Run a saved task's prompt again.")
    task_rerun.add_argument("task_id")
    _add_agent_run_args(task_rerun)

    resume = sub.add_parser("resume", help="Continue after an approval.")
    resume.add_argument("project_id")

    approve = sub.add_parser("approve", help="Approve a deliverable.")
    approve.add_argument("project_id")
    approve.add_argument("deliverable")
    approve.add_argument("--note", default=None)

    reject = sub.add_parser("reject", help="Send a deliverable back.")
    reject.add_argument("project_id")
    reject.add_argument("deliverable")
    reject.add_argument("--note", default=None)

    submit = sub.add_parser(
        "submit",
        help="Submit work for an activity assigned to a human or tool.",
    )
    submit.add_argument("project_id")
    submit.add_argument("activity", help="The activity key.")
    submit.add_argument("--file", default=None, help="Read the work from a file.")
    submit.add_argument("--text", default=None, help="Provide the work inline.")

    web = sub.add_parser("serve", help="Open the web review interface.")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)

    sub.add_parser("list", help="List saved engagements.")

    show = sub.add_parser("show", help="Show an engagement or a deliverable.")
    show.add_argument("project_id")
    show.add_argument("deliverable", nargs="?", default=None)

    export = sub.add_parser(
        "export",
        help="Bundle an engagement's deliverables into one HTML pack.",
    )
    export.add_argument("project_id")
    export.add_argument(
        "--output", default=None, help="Folder to write the pack (default: workspace)."
    )
    export.add_argument(
        "--format",
        default="auto",
        choices=["auto", "docx", "pptx", "eml", "markdown"],
        help="Force a format for every deliverable, or 'auto' per the methodology.",
    )

    return parser


def use_utf8_output() -> None:
    """
    Windows consoles default to cp1252, which cannot encode characters that
    routinely appear in generated content and authored methodologies. A
    console encoding is not a reason to lose an engagement's output.
    """
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    use_utf8_output()

    args = build_parser().parse_args(argv)
    settings = Settings.load()

    configure_logging(settings.log_level, Path(settings.log_file))

    mission_handlers = {
        "add": command_mission_add,
        "list": command_mission_list,
        "show": command_mission_show,
        "edit": command_mission_edit,
        "delete": command_mission_delete,
    }

    methodology_handlers = {
        "list": command_methodology_list,
        "show": command_methodology_show,
        "techniques": command_methodology_techniques,
    }

    task_handlers = {
        "list": command_task_list,
        "show": command_task_show,
        "rerun": command_task_rerun,
    }

    handlers = {
        "methodology": lambda: methodology_handlers[args.methodology_command](
            args, settings
        ),
        "mission": lambda: mission_handlers[args.mission_command](args, settings),
        "launch": lambda: command_launch(args, settings),
        "run": lambda: command_run(args, settings),
        "do": lambda: command_do(args, settings),
        "tools": lambda: command_tools(args, settings),
        "task": lambda: task_handlers[args.task_command](args, settings),
        "resume": lambda: command_resume(args, settings),
        "submit": lambda: command_submit(args, settings),
        "serve": lambda: command_serve(args, settings),
        "approve": lambda: command_review(args, settings, approve=True),
        "reject": lambda: command_review(args, settings, approve=False),
        "list": lambda: command_list(args, settings),
        "show": lambda: command_show(args, settings),
        "export": lambda: command_export(args, settings),
    }

    try:
        return handlers[args.command]()
    except (
        FileNotFoundError,
        KeyError,
        ValueError,
        MissionStateError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
