"""
Command line interface for running and reviewing engagements.

This is the human-in-the-loop seam. Hyperium executes until it produces a
deliverable, then stops and waits here for a person to approve or reject.
"""

from __future__ import annotations

import argparse
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


def build_context(settings: Settings):
    provider = ResilientProvider(
        OllamaProvider(
            model=settings.model,
            timeout_seconds=settings.llm_timeout_seconds,
            temperature=settings.temperature,
        ),
        attempts=settings.llm_attempts,
        backoff_seconds=settings.llm_backoff_seconds,
    )

    methodologies = build_methodologies(settings)

    repository = ProjectRepository(settings.state_directory)
    store = FileArtifactStore(settings.workspace)

    service = ProjectBuilder.build(
        provider,
        store,
        repository=repository,
        methodologies=methodologies,
        default_methodology=settings.default_methodology,
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

    report(backlog.launch(mission.id, resources=[default_resource(settings)]))

    return 0


AGENT_SYSTEM = (
    "You are Hyperium, an autonomous assistant that completes tasks on the "
    "user's behalf. You have tools to read files, list directories and fetch "
    "URLs. Use them to gather facts before answering — never guess at a file's "
    "contents or a page's text. When you have enough information, give a clear, "
    "complete answer. Do not describe what you would do; do it, then report "
    "the result."
)


def command_do(args, settings: Settings) -> int:
    """
    Hand the agent a task; it uses tools and reports the result.

    This is the direct-task path: no mission or methodology. By default the
    tools are read-only and the run is safe unattended. With --allow-writes the
    agent may also change the filesystem, and every such action is held at the
    approval gate — interactively by default, or auto-approved for a trusted
    unattended run.
    """
    from application.agent.agent_runner import AgentRunner
    from application.agent.approval_policies import AutoApproveApprover
    from core.agents.agent_result import StopReason
    from infrastructure.llm.ollama_agent_provider import OllamaAgentProvider
    from infrastructure.tools import read_only_tools, writable_tools
    from interfaces.approval import ConsoleApprover

    root = Path(args.root).resolve()

    if args.allow_writes:
        tools = writable_tools(root)
        approver = AutoApproveApprover() if args.auto_approve else ConsoleApprover()
    else:
        tools = read_only_tools(root)
        approver = None

    runner = AgentRunner(
        OllamaAgentProvider(
            model=settings.model,
            timeout_seconds=settings.llm_timeout_seconds,
            temperature=settings.temperature,
        ),
        tools,
        max_iterations=args.max_steps,
        approver=approver,
    )

    result = runner.run(args.task, system=AGENT_SYSTEM)

    if args.verbose and result.steps:
        print("Steps:")
        for step in result.steps:
            preview = step.result.replace("\n", " ")[:100]
            print(f"  - {step.tool}({step.arguments}) -> {preview}")
        print()

    print(result.output)

    if result.stop_reason is StopReason.MAX_ITERATIONS:
        print(
            "\n(Stopped: reached the step limit. Raise it with --max-steps.)",
            file=sys.stderr,
        )
        return 1

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


def command_serve(args, settings: Settings) -> int:
    from interfaces.web.server import ReviewApp, serve

    service, repository = build_context(settings)

    app = ReviewApp(
        service,
        repository,
        missions=build_backlog(settings),
        methodologies=build_methodologies(settings),
        resources=lambda: [default_resource(settings)],
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

    do = sub.add_parser(
        "do",
        help="Give the agent a task; it uses tools and reports the result.",
    )
    do.add_argument("task", help="The task, in plain language.")
    do.add_argument(
        "--root",
        default=".",
        help="Directory the file tools are confined to (default: current).",
    )
    do.add_argument(
        "--max-steps",
        type=int,
        default=12,
        dest="max_steps",
        help="Maximum tool-using steps before the run is cut short.",
    )
    do.add_argument(
        "--allow-writes",
        action="store_true",
        dest="allow_writes",
        help="Let the agent change files. Each write is held for approval.",
    )
    do.add_argument(
        "--auto-approve",
        action="store_true",
        dest="auto_approve",
        help="Approve every action without asking. Unattended runs only.",
    )
    do.add_argument(
        "--verbose",
        action="store_true",
        help="Show each tool call before the answer.",
    )

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

    handlers = {
        "methodology": lambda: methodology_handlers[args.methodology_command](
            args, settings
        ),
        "mission": lambda: mission_handlers[args.mission_command](args, settings),
        "launch": lambda: command_launch(args, settings),
        "run": lambda: command_run(args, settings),
        "do": lambda: command_do(args, settings),
        "resume": lambda: command_resume(args, settings),
        "submit": lambda: command_submit(args, settings),
        "serve": lambda: command_serve(args, settings),
        "approve": lambda: command_review(args, settings, approve=True),
        "reject": lambda: command_review(args, settings, approve=False),
        "list": lambda: command_list(args, settings),
        "show": lambda: command_show(args, settings),
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
