from __future__ import annotations

from core.execution.activity import Activity
from core.execution.deliverable import Deliverable
from core.execution.deliverable_version import DeliverableVersion
from core.execution.prompting.capability_prompt_library import (
    CapabilityPrompt,
    prompt_for,
)
from core.missions.mission import Mission

_MAX_UPSTREAM_CHARS = 4000


class ActivityPromptBuilder:
    """
    Assembles the prompt that produces one activity's contribution.

    Upstream outputs are included verbatim. That is the point of the
    dependency graph: work compounds because the architect actually reads the
    requirements rather than re-inventing them.
    """

    def __init__(self, techniques=None) -> None:
        """
        `techniques` is any object exposing `technique(key)`. The builder works
        without one; the technique guidance is simply omitted.
        """
        self._techniques = techniques

    def build(
        self,
        activity: Activity,
        deliverable: Deliverable,
        mission: Mission,
        upstream: list[Activity] | None = None,
        revision_of: DeliverableVersion | None = None,
    ) -> str:
        capability = self._primary_capability(activity)

        return "\n".join(
            part
            for part in [
                f"You are {capability.persona}.",
                "",
                capability.guidance,
                "",
                "# Engagement",
                f"Mission: {mission.title}",
                f"Objective: {mission.objective.description}",
                "",
                "# Deliverable",
                f"{deliverable.name}",
                deliverable.description or "",
                self._structure_section(deliverable),
                "",
                "# Your activity",
                f"{activity.name}",
                activity.description or "",
                "",
                self._technique_section(activity),
                self._upstream_section(upstream or []),
                self._revision_section(revision_of),
                "# Instructions",
                "Write only the content for your activity, in Markdown.",
                "Do not restate the instructions or describe what you will do.",
                "Start directly with the content. Use '##' as the top heading "
                "level so the section nests inside the deliverable.",
            ]
            if part is not None
        )

    def _structure_section(self, deliverable: Deliverable) -> str:
        """
        A template defines structure, never content (03-methodologies.md).
        """
        if not deliverable.sections:
            return ""

        lines = ["", "The finished deliverable is expected to cover:"]
        lines.extend(f"- {section}" for section in deliverable.sections)
        lines.append(
            "Contribute the parts that fall to your activity; another "
            "activity may cover the rest."
        )

        return "\n".join(lines)

    def _technique_section(self, activity: Activity) -> str:
        if not activity.technique or self._techniques is None:
            return ""

        technique = self._techniques.technique(activity.technique)

        if technique is None:
            return ""

        blocks = [f"# Technique: {technique.name}", ""]

        if technique.description:
            blocks.extend([technique.description, ""])

        if technique.guidance:
            blocks.extend([technique.guidance, ""])

        return "\n".join(blocks)

    def _revision_section(self, version: DeliverableVersion | None) -> str:
        """
        A rejection is only useful if the feedback reaches the model.
        """
        if version is None:
            return ""

        blocks = [
            "# Revision requested",
            "",
            f"A reviewer read version {version.version} and sent it back.",
            "",
        ]

        if version.review_summary:
            blocks.extend(
                [
                    "Their feedback:",
                    "",
                    version.review_summary,
                    "",
                ]
            )

        blocks.extend(
            [
                "The version they rejected:",
                "",
                self._truncate(version.content),
                "",
                "Rewrite your section to address the feedback directly. Keep "
                "what was working; change what was criticised.",
                "",
            ]
        )

        return "\n".join(blocks)

    def _primary_capability(self, activity: Activity) -> CapabilityPrompt:
        """
        Deterministic pick so that a re-run produces the same persona.
        """
        names = sorted(
            requirement.capability.name
            for requirement in activity.required_capabilities
        )

        if not names:
            return prompt_for("")

        return prompt_for(names[0].replace(" ", "_"))

    def _upstream_section(self, upstream: list[Activity]) -> str:
        completed = [
            activity
            for activity in upstream
            if activity.is_completed and activity.output
        ]

        if not completed:
            return ""

        blocks = ["# Work already completed", ""]

        for activity in completed:
            blocks.append(f"## {activity.name}")
            blocks.append(self._truncate(activity.output or ""))
            blocks.append("")

        blocks.append(
            "Build on the work above. Do not repeat it and do not "
            "contradict it."
        )
        blocks.append("")

        return "\n".join(blocks)

    def _truncate(self, text: str) -> str:
        if len(text) <= _MAX_UPSTREAM_CHARS:
            return text

        return text[:_MAX_UPSTREAM_CHARS] + "\n\n[...truncated]"
