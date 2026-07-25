from pathlib import Path

from core.resources.agents.planning_agent import PlanningAgent
from core.agent_type import AgentType
from core.entities.project import Project
from core.entities.work_item import WorkItem
from application.registry.agent_registry import AgentRegistry
from application.runtime.runtime import Runtime

project = Project(
    name="Business Analysis Academy",
    goal="Create the best Business Analysis Academy available.",
    workspace=Path("workspace"),
)

planner = PlanningAgent()

planning_task = WorkItem(
    title="Create a complete execution plan.",
    assigned_agent=AgentType.PLANNING,
)

plan = planner.execute(
    project,
    planning_task,
)

project.work_items.extend(plan.new_work_items)
project.deliverables.extend(plan.deliverables)

registry = AgentRegistry()

runtime = Runtime(
    registry=registry,
)

runtime.run(project)
