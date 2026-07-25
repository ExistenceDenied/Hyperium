from enum import Enum


class DeliverableStatus(str, Enum):
    """
    Lifecycle of a deliverable, including the human approval gate.

    A deliverable moves to AWAITING_APPROVAL once every activity that produces
    it has completed. It never advances past that point without an explicit
    human decision.
    """

    DRAFT = "DRAFT"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
