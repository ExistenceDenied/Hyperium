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
from core.missions.mission import Mission
from core.project.project import Project
from core.resources.ai_resource import AIResource
from core.resources.human_resource import HumanResource
from core.resources.resource import Resource
from infrastructure.persistence.mission_serializer import MissionSerializer

# 2: the embedded mission gained backlog identity and lifecycle.
# 3: methodologies — deliverables carry a stage and sections, activities carry
#    a technique, and the plan records which methodology produced it.
SCHEMA_VERSION = 3

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

    def __init__(
        self,
        missions: MissionSerializer | None = None,
        methodologies=None,
    ) -> None:
        self._missions = missions or MissionSerializer()
        # Methodologies are authored data, not project state: the plan stores
        # the key and the definition is resolved from the registry on load.
        self._methodologies = methodologies

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
        version = payload.get("schema_version")

        if version != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported project schema version {version!r}; "
                f"expected {SCHEMA_VERSION}."
            )

        deliverables = [
            self._read_deliverable(entry)
            for entry in payload.get("analysis", {}).get("deliverables", [])
        ]

        by_key = {item.key: item for item in deliverables}

        project = Project(
            id=UUID(payload["id"]),
            mission=self._read_mission(payload["mission"]),
            analysis=self._read_analysis(payload.get("analysis"), deliverables),
            execution_plan=self._read_plan(
                payload.get("execution_plan"), by_key
            ),
            execution_result=self._read_result(payload.get("execution_result")),
        )

        return project

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
            "deliverables": [
                self._deliverable(item) for item in analysis.deliverables
            ],
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
            "methodology": (
                plan.methodology.key if plan.methodology else None
            ),
            "activity_order": [activity.key for activity in plan.activities],
            "deliverable_order": [item.key for item in plan.deliverables],
            "allocations": [
                {
                    "activity_key": activity.key,
                    "resource": self._resource(plan.allocations[activity.id]),
                }
                for activity in plan.activities
                if activity.id in plan.allocations
            ],
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
        deliverables: list[Deliverable],
    ) -> AnalysisResult | None:
        if payload is None:
            return None

        return AnalysisResult(
            summary=payload.get("summary", ""),
            assumptions=list(payload.get("assumptions", [])),
            risks=list(payload.get("risks", [])),
            deliverables=deliverables,
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
        deliverables: dict[str, Deliverable],
    ) -> ExecutionPlan | None:
        if payload is None:
            return None

        by_key = {
            activity.key: activity
            for deliverable in deliverables.values()
            for activity in deliverable.activities
        }

        plan = ExecutionPlan(
            deliverables=[
                deliverables[key]
                for key in payload.get("deliverable_order", [])
                if key in deliverables
            ]
        )

        for key in payload.get("activity_order", []):
            if key in by_key:
                plan.add_activity(by_key[key])

        for entry in payload.get("allocations", []):
            activity = by_key.get(entry["activity_key"])

            if activity is not None:
                plan.assign(activity, self._read_resource(entry["resource"]))

        plan.methodology = self._read_methodology(payload.get("methodology"))

        return plan

    def _read_methodology(self, key: str | None):
        if not key or self._methodologies is None:
            return None

        try:
            return self._methodologies.get(key)
        except KeyError:
            # A methodology may have been renamed or removed since the
            # engagement was planned. The saved plan still holds every
            # activity, so the engagement remains resumable without gates.
            return None

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
