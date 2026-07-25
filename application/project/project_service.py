from application.analysis.analysis_service import AnalysisService
from application.execution.execution_engine import ExecutionEngine
from application.planning.planning_application_service import (
    PlanningApplicationService,
)
from core.missions.mission import Mission
from core.project.project import Project
from core.resources.resource import Resource


class ProjectService:
    """
    Orchestrates the complete project lifecycle.
    """

    def __init__(
        self,
        analysis_service: AnalysisService,
        planning_service: PlanningApplicationService,
        execution_engine: ExecutionEngine,
    ) -> None:
        self._analysis_service = analysis_service
        self._planning_service = planning_service
        self._execution_engine = execution_engine

    def execute(
        self,
        mission: Mission,
        resources: list[Resource],
    ) -> Project:
        project = Project.from_mission(mission)

        project.analysis = self._analysis_service.analyze(mission)

        project.execution_plan = self._planning_service.create_execution_plan(
            project.analysis,
            resources,
        )

        project.execution_result = self._execution_engine.execute(
            project.execution_plan
        )

        return project