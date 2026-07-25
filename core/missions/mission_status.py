from enum import Enum


class MissionStatus(str, Enum):
    """
    Lifecycle of a mission in the backlog.

    A mission is DRAFT while it is being written and may be incomplete.
    Validation is deferred to launch, so an idea can be captured in one line
    and refined later rather than being rejected on the way in.
    """

    DRAFT = "DRAFT"
    READY = "READY"
    LAUNCHED = "LAUNCHED"
    ARCHIVED = "ARCHIVED"
