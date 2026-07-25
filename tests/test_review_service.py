from core.review.review_result import ReviewResult
from core.review.review_status import ReviewStatus
from services.review_service import ReviewService


def test_review_service_approves_high_score():
    service = ReviewService()

    review = ReviewResult(
        status=ReviewStatus.CHANGES_REQUIRED,
        score=100,
        reviewer="Reviewer",
        summary="Excellent work.",
    )

    result = service.review(review)

    assert result.status == ReviewStatus.APPROVED
    assert result.score == 100


def test_review_service_preserves_follow_up_work_items():
    service = ReviewService()

    review = ReviewResult(
        status=ReviewStatus.CHANGES_REQUIRED,
        score=100,
        reviewer="Reviewer",
        summary="Excellent work.",
    )

    result = service.review(review)

    assert len(result.follow_up_work_items) == 0