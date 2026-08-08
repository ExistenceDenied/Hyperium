from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from core.analysis.analysis_result import AnalysisResult
from core.capabilities.capability import Capability
from core.capabilities.capability_requirement import CapabilityRequirement
from core.capabilities.proficiency_level import ProficiencyLevel
from core.execution.activity import Activity
from core.execution.activity_status import ActivityStatus
from core.execution.deliverable import Deliverable
from core.execution.deliverable_status import DeliverableStatus
from core.execution.deliverable_version import DeliverableVersion
from core.execution.execution_plan import ExecutionPlan
from core.execution.execution_result import ExecutionResult, ExecutionStatus
from core.execution.stage_plan import StagePlan
from core.methodologies.quality_gate import QualityGate
from core.missions.mission import Mission
from core.project.project import Project
from core.resources.ai_resource import AIResource
from core.resources.human_resource import HumanResource
from core.resources.resource import Resource
from infrastructure.persistence.migrations import upgrade
from infrastructure.persistence.mission_serializer import MissionSerializer

# 2: the embedded mission gained backlog identity and lifecycle.
# 3: methodologies — deliverables carry a stage and sections, activities carry
#    a technique, and the plan records which methodology produced it.
# 4: the plan owns its deliverables and its stages, including the quality
#    gates it was planned with. The analysis no longer carries deliverables.
SCHEMA_VERSION = 4

_RESOURCE_TYPES: dict[str, type[Resource]] = {
    "AIResource": AIResource,
    "HumanResource": HumanResource,
}


class ProjectSerializer:
    """
    Converts a Project to and from plain dictionaries.

    Serialisation lives in infrastructure so that the domain stays free of
    storage concerns. The whole object graph round-trips, including activity
    status and deliverable versions, because that is what makes a paused
    engagement resumable.
    """

    def __init__(self, missions: MissionSerializer | None = None) -> None:
        self._missions = missions or MissionSerializer()

    def to_dict(self, project: Project) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "id": str(project.id),
            "mission": self._mission(project.mission),
            "analysis": self._analysis(project.analysis),
            "execution_plan": self._plan(project.execution_plan),
            "execution_result": self._result(project.execution_result),
        }

    def from_dict(self, payload: dict[str, Any]) -> Project:
        # Older files are upgraded rather than refused. A schema bump should
        # not cost anyone their engagement.
        payload = upgrade(payload, SCHEMA_VERSION)

        return Project(
            id=UUID(payload["id"]),
            mission=self._read_mission(payload["mission"]),
            analysis=self._read_analysis(payload.get("analysis")),
            execution_plan=self._read_plan(payload.get("execution_plan")),
            execution_result=self._read_result(payload.get("execution_result")),
        )

    # ---------------------------------------------------------------- write

    def _mission(self, mission: Mission) -> dict[str, Any]:
        return self._missions.to_dict(mission)

    def _analysis(self, analysis: AnalysisResult | None) -> dict[str, Any] | None:
        if analysis is None:
            return None

        return {
            "summary": analysis.summary,
            "assumptions": list(analysis.assumptions),
            "risks": list(analysis.risks),
            "recommended_methodology": analysis.recommended_methodology,
            "rationale": analysis.rationale,
        }

    def _deliverable(self, deliverable: Deliverable) -> dict[str, Any]:
        return {
            "key": deliverable.key,
            "id": str(deliverable.id),
            "name": deliverable.name,
            "description": deliverable.description,
            "status": deliverable.status.value,
            "stage": deliverable.stage,
            "sections": list(deliverable.sections),
            "activities": [
                self._activity(item) for item in deliverable.activities
            ],
            "versions": [self._version(item) for item in deliverable.versions],
        }

    def _activity(self, activity: Activity) -> dict[str, Any]:
        return {
            "key": activity.key,
            "id": str(activity.id),
            "name": activity.name,
            "description": activity.description,
            "status": activity.status.value,
            "output": activity.output,
            "technique": activity.technique,
            "depends_on": sorted(activity.depends_on),
            "required_capabilities": [
                {
                    "name": requirement.capability.name,
                    "description": requirement.capability.description,
                    "minimum_level": int(requirement.minimum_level),
                    "mandatory": requirement.mandatory,
                }
                for requirement in sorted(
                    activity.required_capabilities,
                    key=lambda item: item.capability.name,
                )
            ],
        }

    def _version(self, version: DeliverableVersion) -> dict[str, Any]:
        return {
            "version": version.version,
            "content": version.content,
            "filename": version.filename,
            "created_by": version.created_by,
            "created_at": version.created_at.isoformat(),
            "review_summary": version.review_summary,
        }

    def _plan(self, plan: ExecutionPlan | None) -> dict[str, Any] | None:
        if plan is None:
            return None

        return {
            "methodology_key": plan.methodology_key,
            "deliverables": [
                self._deliverable(item) for item in plan.deliverables
            ],
            "stages": [self._stage(item) for item in plan.stages],
            "activity_order": [activity.key for activity in plan.activities],
            "allocations": [
                {
                    "activity_key": activity.key,
                    "resource": self._resource(plan.allocations[activity.id]),
                }
                for activity in plan.activities
                if activity.id in plan.allocations
            ],
        }

    def _stage(self, stage: StagePlan) -> dict[str, Any]:
        gate = stage.quality_gate

        return {
            "key": stage.key,
            "name": stage.name,
            "depends_on": list(stage.depends_on),
            "quality_gate": (
                {
                    "description": gate.description,
                    "require_approval": gate.require_approval,
                    "minimum_words": gate.minimum_words,
                    "required_sections": list(gate.required_sections),
                }
                if gate
                else None
            ),
        }

    def _resource(self, resource: Resource) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": type(resource).__name__,
            "name": resource.name,
            "capabilities": [
                {
                    "name": capability.name,
                    "description": capability.description,
                    "level": int(level),
                }
                for capability, level in resource.capabilities.items()
            ],
        }

        if isinstance(resource, AIResource):
            payload["provider"] = resource.provider
            payload["model"] = resource.model

        return payload

    def _result(self, result: ExecutionResult | None) -> dict[str, Any] | None:
        if result is None:
            return None

        return {
            "started_at": result.started_at.isoformat(),
            "completed_at": (
                result.completed_at.isoformat() if result.completed_at else None
            ),
            "status": result.status.value,
            "messages": list(result.messages),
            "activities_executed": result.activities_executed,
            "deliverables_produced": list(result.deliverables_produced),
        }

    # ----------------------------------------------------------------- read

    def _read_mission(self, payload: dict[str, Any]) -> Mission:
        return self._missions.from_dict(payload)

    def _read_analysis(
        self,
        payload: dict[str, Any] | None,
    ) -> AnalysisResult | None:
        if payload is None:
            return None

        return AnalysisResult(
            summary=payload.get("summary", ""),
            assumptions=list(payload.get("assumptions", [])),
            risks=list(payload.get("risks", [])),
            recommended_methodology=payload.get("recommended_methodology"),
            rationale=payload.get("rationale", ""),
        )

    def _read_deliverable(self, payload: dict[str, Any]) -> Deliverable:
        return Deliverable(
            key=payload["key"],
            id=UUID(payload["id"]),
            name=payload["name"],
            description=payload.get("description"),
            status=DeliverableStatus(payload["status"]),
            stage=payload.get("stage"),
            sections=tuple(payload.get("sections", [])),
            activities=[
                self._read_activity(entry)
                for entry in payload.get("activities", [])
            ],
            versions=[
                self._read_version(entry)
                for entry in payload.get("versions", [])
            ],
        )

    def _read_activity(self, payload: dict[str, Any]) -> Activity:
        return Activity(
            key=payload["key"],
            id=UUID(payload["id"]),
            name=payload["name"],
            description=payload.get("description", ""),
            status=ActivityStatus(payload["status"]),
            output=payload.get("output"),
            technique=payload.get("technique"),
            depends_on=set(payload.get("depends_on", [])),
            required_capabilities={
                CapabilityRequirement(
                    capability=Capability(
                        name=entry["name"],
                        description=entry.get("description", ""),
                    ),
                    minimum_level=ProficiencyLevel(entry["minimum_level"]),
                    mandatory=entry.get("mandatory", True),
                )
                for entry in payload.get("required_capabilities", [])
            },
        )

    def _read_version(self, payload: dict[str, Any]) -> DeliverableVersion:
        return DeliverableVersion(
            version=payload["version"],
            content=payload["content"],
            filename=payload["filename"],
            created_by=payload.get("created_by", ""),
            created_at=datetime.fromisoformat(payload["created_at"]),
            review_summary=payload.get("review_summary"),
        )

    def _read_plan(
        self,
        payload: dict[str, Any] | None,
    ) -> ExecutionPlan | None:
        if payload is None:
            return None

        deliverables = [
            self._read_deliverable(entry)
            for entry in payload.get("deliverables", [])
        ]

        by_key = {
            activity.key: activity
            for deliverable in deliverables
            for activity in deliverable.activities
        }

        plan = ExecutionPlan(
            deliverables=deliverables,
            stages=[self._read_stage(entry) for entry in payload.get("stages", [])],
            methodology_key=payload.get("methodology_key"),
        )

        for key in payload.get("activity_order", []):
            activity = by_key.get(key)

            if activity is None:
                # Silently dropping work would leave an engagement quietly
                # smaller than the one that was saved.
                raise ValueError(
                    f"Saved plan references activity '{key}', which no "
                    f"deliverable in the file provides."
                )

            plan.add_activity(activity)

        for entry in payload.get("allocations", []):
            activity = by_key.get(entry["activity_key"])

            if activity is not None:
                plan.assign(activity, self._read_resource(entry["resource"]))

        return plan

    def _read_stage(self, payload: dict[str, Any]) -> StagePlan:
        gate = payload.get("quality_gate")

        return StagePlan(
            key=payload["key"],
            name=payload.get("name", ""),
            depends_on=tuple(payload.get("depends_on", [])),
            quality_gate=(
                QualityGate(
                    description=gate.get("description", ""),
                    require_approval=gate.get("require_approval", True),
                    minimum_words=int(gate.get("minimum_words", 0)),
                    required_sections=tuple(gate.get("required_sections", [])),
                )
                if gate
                else None
            ),
        )

    def _read_resource(self, payload: dict[str, Any]) -> Resource:
        resource_type = _RESOURCE_TYPES.get(payload["type"], AIResource)

        kwargs: dict[str, Any] = {"name": payload["name"]}

        if resource_type is AIResource:
            kwargs["provider"] = payload.get("provider", "")
            kwargs["model"] = payload.get("model", "")

        resource = resource_type(**kwargs)

        for entry in payload.get("capabilities", []):
            resource.add_capability(
                Capability(
                    name=entry["name"],
                    description=entry.get("description", ""),
                ),
                ProficiencyLevel(entry["level"]),
            )

        return resource

    def _read_result(
        self,
        payload: dict[str, Any] | None,
    ) -> ExecutionResult | None:
        if payload is None:
            return None

        return ExecutionResult(
            started_at=datetime.fromisoformat(payload["started_at"]),
            completed_at=(
                datetime.fromisoformat(payload["completed_at"])
                if payload.get("completed_at")
                else None
            ),
            status=ExecutionStatus(payload["status"]),
            messages=list(payload.get("messages", [])),
            activities_executed=payload.get("activities_executed", 0),
            deliverables_produced=list(payload.get("deliverables_produced", [])),
        )
