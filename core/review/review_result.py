from dataclasses import dataclass, field

from core.review.review_comment import ReviewComment
from core.review.review_status import ReviewStatus
from core.entities.work_item import WorkItem


@dataclass
class ReviewResult:

    status: ReviewStatus

    score: int

    reviewer: str

    summary: str

    comments: list[ReviewComment] = field(default_factory=list)

    follow_up_work_items: list[WorkItem] = field(default_factory=list)