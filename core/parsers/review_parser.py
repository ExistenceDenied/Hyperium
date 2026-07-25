import json

from core.review.review_result import ReviewResult
from core.review.review_status import ReviewStatus


def parse_review(text: str) -> ReviewResult:

    data = json.loads(text)

    return ReviewResult(
        status=(
            ReviewStatus.APPROVED
            if data["score"] >= 80
            else ReviewStatus.REJECTED
        ),
        score=data["score"],
        reviewer="Reviewer",
        summary=data["summary"],
        comments=[],
        follow_up_work_items=[],
    )