from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from core.execution.activity import Activity
from core.execution.deliverable_status import DeliverableStatus
from core.execution.deliverable_version import DeliverableVersion

_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    return _SLUG.sub("-", value.strip().lower()).strip("-") or "deliverable"


@dataclass
class Deliverable:
    """
    Represents a business deliverable consisting of one or more activities.

    A deliverable is both the work breakdown (its activities) and the artifact
    those activities produce (its versions). Every revision creates a new
    version with its own filename, so the version that was reviewed is never
    overwritten by the one that replaces it.
    """

    key: str = ""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str | None = None
    activities: list[Activity] = field(default_factory=list)
    versions: list[DeliverableVersion] = field(default_factory=list)
    status: DeliverableStatus = DeliverableStatus.DRAFT
    stage: str | None = None
    sections: tuple[str, ...] = ()

    def add_activity(self, activity: Activity) -> None:
        if activity not in self.activities:
            self.activities.append(activity)

    def add_version(
        self,
        content: str,
        created_by: str = "",
    ) -> DeliverableVersion:
        number = len(self.versions) + 1

        version = DeliverableVersion(
            version=number,
            content=content,
            filename=f"{self.key or slugify(self.name)}-v{number}.md",
            created_by=created_by,
        )

        self.versions.append(version)

        return version

    def latest_version(self) -> DeliverableVersion | None:
        return self.versions[-1] if self.versions else None

    @property
    def is_complete(self) -> bool:
        """Every activity producing this deliverable has finished."""
        return bool(self.activities) and all(
            activity.is_completed for activity in self.activities
        )

    @property
    def is_approved(self) -> bool:
        return self.status is DeliverableStatus.APPROVED

    def submit_for_approval(self) -> None:
        self.status = DeliverableStatus.AWAITING_APPROVAL

    def approve(self, summary: str | None = None) -> None:
        self.status = DeliverableStatus.APPROVED
        self._record_review(summary)

    def request_changes(self, summary: str | None = None) -> None:
        """
        Send the deliverable back for rework.

        The activities are reset so the next execution pass regenerates the
        content, informed by the reviewer's feedback and the version being
        replaced. Without this reset a rejection is a dead end: the activities
        stay COMPLETED, nothing re-runs, and the engagement blocks forever.
        """
        self.status = DeliverableStatus.CHANGES_REQUESTED
        self._record_review(summary)

        for activity in self.activities:
            activity.reset()

    def _record_review(self, summary: str | None) -> None:
        version = self.latest_version()

        if version is not None and summary:
            version.review_summary = summary
