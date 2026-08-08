from __future__ import annotations

from dataclasses import dataclass, field

from core.methodologies.quality_gate import QualityGate


class MethodologyError(ValueError):
    """
    Raised when a methodology is internally inconsistent.
    """


@dataclass(frozen=True)
class ActivityTemplate:
    """
    A unit of work a methodology prescribes.

    This is the template; `Activity` is the instance created for a project.
    """

    key: str
    name: str
    description: str = ""
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    technique: str | None = None
    depends_on: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DeliverableTemplate:
    """
    A deliverable a methodology prescribes, and the shape it should take.

    `sections` is the structure only. Per 03-methodologies.md a template
    defines structure rather than content — the content is generated.
    """

    key: str
    name: str
    description: str = ""
    sections: tuple[str, ...] = field(default_factory=tuple)
    activities: tuple[ActivityTemplate, ...] = field(default_factory=tuple)
    #: The file type a client receives: "markdown", "docx" or "pptx". Structure
    #: only, like `sections` — it shapes the export, never the content.
    format: str = "markdown"


@dataclass(frozen=True)
class Stage:
    """
    A phase of an engagement, gated on the way out.
    """

    key: str
    name: str
    description: str = ""
    depends_on: tuple[str, ...] = field(default_factory=tuple)
    deliverables: tuple[DeliverableTemplate, ...] = field(default_factory=tuple)
    quality_gate: QualityGate | None = None

    @property
    def activities(self) -> tuple[ActivityTemplate, ...]:
        return tuple(
            activity
            for deliverable in self.deliverables
            for activity in deliverable.activities
        )


@dataclass(frozen=True)
class Methodology:
    """
    A reusable blueprint for solving a category of business problem.

    A Methodology carries no project-specific state: the same one may be used
    by thousands of projects. It is the platform's primary asset, and the
    reason Hyperium determines the execution structure rather than the model.
    """

    key: str
    name: str
    description: str = ""
    version: str = "1.0"
    discipline: str = ""
    principles: tuple[str, ...] = field(default_factory=tuple)
    stages: tuple[Stage, ...] = field(default_factory=tuple)

    @property
    def deliverables(self) -> tuple[DeliverableTemplate, ...]:
        return tuple(
            deliverable
            for stage in self.stages
            for deliverable in stage.deliverables
        )

    @property
    def activities(self) -> tuple[ActivityTemplate, ...]:
        return tuple(
            activity for stage in self.stages for activity in stage.activities
        )

    def stage(self, key: str) -> Stage:
        for stage in self.stages:
            if stage.key == key:
                return stage

        raise KeyError(f"No stage '{key}' in methodology '{self.key}'.")

    def stage_of(self, activity_key: str) -> Stage | None:
        for stage in self.stages:
            for activity in stage.activities:
                if activity.key == activity_key:
                    return stage

        return None

    def validate(self) -> None:
        """
        Reject a methodology that could not produce an executable plan.

        Authoring errors surface here, once, at load time — rather than
        halfway through an engagement.
        """
        if not self.stages:
            raise MethodologyError(
                f"Methodology '{self.key}' defines no stages."
            )

        self._unique(
            [stage.key for stage in self.stages], "stage"
        )
        self._unique(
            [item.key for item in self.deliverables], "deliverable"
        )
        self._unique(
            [item.key for item in self.activities], "activity"
        )

        stage_keys = {stage.key for stage in self.stages}
        activity_keys = {activity.key for activity in self.activities}

        for stage in self.stages:
            if stage.key in stage.depends_on:
                raise MethodologyError(
                    f"Stage '{stage.key}' depends on itself."
                )

            for dependency in stage.depends_on:
                if dependency not in stage_keys:
                    raise MethodologyError(
                        f"Stage '{stage.key}' depends on unknown stage "
                        f"'{dependency}'."
                    )

            if not stage.deliverables:
                raise MethodologyError(
                    f"Stage '{stage.key}' defines no deliverables."
                )

            for deliverable in stage.deliverables:
                if not deliverable.activities:
                    raise MethodologyError(
                        f"Deliverable '{deliverable.key}' defines no "
                        f"activities."
                    )

        for activity in self.activities:
            if not activity.capabilities:
                raise MethodologyError(
                    f"Activity '{activity.key}' requires no capabilities and "
                    f"could never be allocated."
                )

            if activity.key in activity.depends_on:
                raise MethodologyError(
                    f"Activity '{activity.key}' depends on itself."
                )

            for dependency in activity.depends_on:
                if dependency not in activity_keys:
                    raise MethodologyError(
                        f"Activity '{activity.key}' depends on unknown "
                        f"activity '{dependency}'."
                    )

        self._reject_stage_cycles()
        self._reject_backwards_activity_dependencies()

    def _unique(self, keys: list[str], label: str) -> None:
        seen = set()

        for key in keys:
            if not key:
                raise MethodologyError(
                    f"Methodology '{self.key}' has an unnamed {label}."
                )

            if key in seen:
                raise MethodologyError(
                    f"Duplicate {label} key '{key}' in methodology "
                    f"'{self.key}'."
                )

            seen.add(key)

    def _reject_stage_cycles(self) -> None:
        outstanding = {
            stage.key: set(stage.depends_on) for stage in self.stages
        }
        resolved: set[str] = set()

        while True:
            ready = {
                key
                for key, pending in outstanding.items()
                if not pending - resolved
            } - resolved

            if not ready:
                break

            resolved |= ready

        if len(resolved) != len(outstanding):
            blocked = sorted(set(outstanding) - resolved)
            raise MethodologyError(
                f"Stages form a circular dependency: {', '.join(blocked)}."
            )

    def _reject_backwards_activity_dependencies(self) -> None:
        """
        An activity may not depend on work from a later stage.

        Stages exist to order an engagement; an edge that runs backwards
        against them would make the stage sequence a lie.
        """
        order = {stage.key: index for index, stage in enumerate(self.stages)}
        position = {
            activity.key: order[stage.key]
            for stage in self.stages
            for activity in stage.activities
        }

        for activity in self.activities:
            here = position[activity.key]

            for dependency in activity.depends_on:
                if position[dependency] > here:
                    raise MethodologyError(
                        f"Activity '{activity.key}' depends on "
                        f"'{dependency}', which belongs to a later stage."
                    )
