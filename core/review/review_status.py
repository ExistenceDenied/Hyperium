from enum import Enum


class ReviewStatus(str, Enum):

    APPROVED = "approved"

    CHANGES_REQUIRED = "changes_required"

    REJECTED = "rejected"