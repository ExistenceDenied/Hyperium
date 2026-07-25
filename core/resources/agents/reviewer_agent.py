from core.resources.agents.base_agent import BaseAgent
from core.entities.project import Project
from core.entities.work_item import WorkItem
from core.value_objects.agent_result import AgentResult
from services.review_service import ReviewService
from core.entities.deliverable_status import DeliverableStatus
from core.review.review_status import ReviewStatus

class ReviewerAgent(BaseAgent):

    def __init__(self):
        super().__init__("Reviewer")
        self.review_service = ReviewService()

    @property
    def system_prompt(self):
        return """
    You are a senior reviewer.

    Review the supplied document.

    Return ONLY valid JSON.

    Schema:

    {
        "score": <integer between 0 and 100>,
        "summary": "<short summary>"
    }

    Rules:

    - Output ONLY JSON.
    - Do not wrap the JSON in markdown.
    - Do not explain anything.
    """

    def execute(self, project: Project, work_item: WorkItem) -> AgentResult:

        if not work_item.input_files:
            raise ValueError(
                f"Review work item '{work_item.title}' has no input files."
            )

        filename = work_item.input_files[0]

        deliverable = project.get_deliverable(filename)

        if deliverable is None:
            raise ValueError(
                f"Deliverable '{filename}' not found."
            )

        deliverable.status = DeliverableStatus.IN_REVIEW

        document = self.workspace.read(
            project.workspace,
            deliverable.latest_filename(),
        )

        from core.parsers.review_parser import parse_review

        review_json = self.ask(document)
        review_result = parse_review(review_json)
        review_result.reviewer = self.role
        review_result = self.review_service.review(
            review_result
        )

        

        if review_result.status == ReviewStatus.APPROVED:
            deliverable.status = DeliverableStatus.APPROVED
        else:
            deliverable.status = DeliverableStatus.REJECTED

        deliverable.latest_version().review_score = review_result.score
        deliverable.latest_version().review_summary = review_result.summary
        if review_result.status == ReviewStatus.CHANGES_REQUIRED:

            improvement = WorkItem(
                title=f"Improve {deliverable.name}",
                assigned_agent=deliverable.owner,
                objective=review_result.summary,
                input_files=[
                    deliverable.latest_filename()
                ],
                expected_outputs=[
                    deliverable.latest_filename()
                ],
            )

            review_result.follow_up_work_items.append(
                improvement
            )
        return AgentResult(
            deliverables=[],
            new_work_items=review_result.follow_up_work_items,
            observations=[review_result.summary],
        )