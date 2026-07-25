from dataclasses import dataclass

from core.review.review_status import ReviewStatus


@dataclass
class ReviewComment:

    severity: str

    category: str

    message: str