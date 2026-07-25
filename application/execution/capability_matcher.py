from core.capabilities.capability_requirement import CapabilityRequirement
from core.execution.activity import Activity
from core.resources.resource import Resource


class CapabilityMatcher:
    """
    Determines whether a resource satisfies an activity's capability requirements.
    """

    def matches(
        self,
        activity: Activity,
        resource: Resource,
    ) -> bool:
        for requirement in activity.required_capabilities:
            level = resource.proficiency(requirement.capability)

            if level is None:
                if requirement.mandatory:
                    return False
                continue

            if level < requirement.minimum_level:
                return False

        return True