from __future__ import annotations

import logging

from core.capabilities.capability_catalog import CapabilityCatalog
from core.capabilities.capability_requirement import CapabilityRequirement
from core.execution.activity import Activity
from core.execution.deliverable import Deliverable
from core.execution.stage_plan import StagePlan
from core.methodologies.methodology import Methodology
from core.missions.mission import Mission

logger = logging.getLogger(__name__)


class MethodologyPlanner:
    """
    Builds an engagement's work breakdown from a methodology.

    This is the inversion that 2.0 exists for. Previously a language model
    decided what work an engagement contained; now a methodology does, and the
    model is left with the job it is actually good at — writing the content of
    each deliverable.

    The planner is deterministic: the same methodology and mission produce the
    same deliverables, activities, capabilities and dependencies every time.
    """

    def stages(self, methodology: Methodology) -> list[StagePlan]:
        """
        Copy the stage ordering and gates into the plan.

        The plan owns its governance from this point on, so editing or
        deleting the methodology cannot change the rules an engagement
        already in flight is being held to.
        """
        return [
            StagePlan(
                key=stage.key,
                name=stage.name,
                depends_on=tuple(stage.depends_on),
                quality_gate=stage.quality_gate,
            )
            for stage in methodology.stages
        ]

    def build(
        self,
        methodology: Methodology,
        mission: Mission,
    ) -> list[Deliverable]:
        methodology.validate()

        deliverables: list[Deliverable] = []

        for stage in methodology.stages:
            stage_dependencies = self._stage_dependencies(methodology, stage)

            for template in stage.deliverables:
                deliverable = Deliverable(
                    key=template.key,
                    name=template.name,
                    description=template.description or None,
                    stage=stage.key,
                    sections=tuple(template.sections),
                )

                for activity_template in template.activities:
                    deliverable.add_activity(
                        Activity(
                            key=activity_template.key,
                            name=activity_template.name,
                            description=activity_template.description,
                            technique=activity_template.technique,
                            depends_on=set(activity_template.depends_on)
                            | stage_dependencies,
                            required_capabilities=self._requirements(
                                activity_template.capabilities
                            ),
                        )
                    )

                deliverables.append(deliverable)

        logger.info(
            "Planned '%s' from methodology '%s': %s deliverables, "
            "%s activities.",
            mission.title,
            methodology.key,
            len(deliverables),
            sum(len(item.activities) for item in deliverables),
        )

        return deliverables

    def _stage_dependencies(
        self,
        methodology: Methodology,
        stage,
    ) -> set[str]:
        """
        Expand stage ordering into activity edges.

        Every activity in a stage waits on the last activities of the stages
        it depends on. Expressing stage order as ordinary dependencies means
        the existing topological sort enforces it — there is no second
        scheduling mechanism to keep correct.
        """
        dependencies: set[str] = set()

        for key in stage.depends_on:
            upstream = methodology.stage(key)
            dependencies.update(
                activity.key for activity in self._terminal(upstream)
            )

        return dependencies

    def _terminal(self, stage) -> list:
        """
        The activities in a stage that nothing else in that stage depends on.

        Depending on those alone, rather than on every activity, keeps the
        graph small while still ordering the stages correctly.
        """
        activities = list(stage.activities)
        depended_upon = {
            key for activity in activities for key in activity.depends_on
        }

        terminal = [
            activity for activity in activities if activity.key not in depended_upon
        ]

        return terminal or activities

    def _requirements(
        self,
        capabilities: tuple[str, ...],
    ) -> set[CapabilityRequirement]:
        requirements = set()

        for key in capabilities:
            requirements.add(
                CapabilityRequirement(capability=CapabilityCatalog.get(key))
            )

        return requirements
