from enum import Enum


class DeliverableStatus(str, Enum):

    DRAFT = "Draft"

    IN_REVIEW = "In Review"

    APPROVED = "Approved"

    REJECTED = "Rejected"

    ARCHIVED = "Archived"