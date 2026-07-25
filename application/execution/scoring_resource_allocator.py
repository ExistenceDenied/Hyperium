from application.execution.capability_matcher import CapabilityMatcher
from core.execution.activity import Activity
from core.resources.resource import Resource


class ScoringResourceAllocator:
    """
    Selects the best matching resource for an activity.
    """

    def __init__(self, matcher: CapabilityMatcher) -> None:
        self._matcher = matcher

    def allocate(
        self,
        activity: Activity,
        resources: list[Resource],
    ) -> Resource | None:
        candidates = [
            resource
            for resource in resources
            if self._matcher.matches(activity, resource)
        ]

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda resource: len(resource.capabilities),
        )