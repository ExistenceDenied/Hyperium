from core.review.review_result import ReviewResult
from core.review.review_status import ReviewStatus


class ReviewService:

    def review(self, review_result: ReviewResult) -> ReviewResult:

        score = review_result.score

        if score >= 90:
            review_result.status = ReviewStatus.APPROVED

        elif score >= 70:
            review_result.status = ReviewStatus.CHANGES_REQUIRED

        else:
            review_result.status = ReviewStatus.REJECTED

        return review_result