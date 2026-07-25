from enum import Enum


class ActivityStatus(str, Enum):
    """
    Lifecycle of a single activity.

    BLOCKED is derived rather than stored: an activity is blocked when one of
    its dependencies has not COMPLETED, or when the deliverable that dependency
    belongs to is still awaiting human approval.
    """

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
