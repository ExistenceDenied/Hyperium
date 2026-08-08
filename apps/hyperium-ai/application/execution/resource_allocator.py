from application.execution.capability_matcher import CapabilityMatcher
from core.execution.activity import Activity
from core.resources.resource import Resource


class ResourceAllocator:
    """
    Allocates the most suitable resource to an activity.
    """

    def __init__(self, matcher: CapabilityMatcher) -> None:
        self._matcher = matcher

    def allocate(
        self,
        activity: Activity,
        resources: list[Resource],
    ) -> Resource | None:
        for resource in resources:
            if self._matcher.matches(activity, resource):
                return resource

        return None