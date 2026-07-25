from datetime import datetime

from core.role_mapper import map_role
from core.entities.deliverable import Deliverable
from core.entities.deliverable_status import DeliverableStatus
from core.entities.deliverable_version import DeliverableVersion
from core.entities.work_item import WorkItem
from core.value_objects.agent_result import AgentResult


def map_planning(data: dict) -> AgentResult:

    deliverables = []

    for item in data["deliverables"]:

        owner = map_role(item["owner"])

        version = DeliverableVersion(
            version=1,
            filename=item["filename"],
            created_by=owner,
            created_at=datetime.now(),
        )

        deliverables.append(
            Deliverable(
                name=item["name"],
                owner=owner,
                status=DeliverableStatus.DRAFT,
                versions=[version],
            )
        )

    work_items = []

    for item in data["tasks"]:

        assigned_agent = map_role(item["assigned_agent"])

        work_items.append(
            WorkItem(
                title=item["title"],
                assigned_agent=assigned_agent,
                objective=item.get("description", ""),
                input_files=item.get("input_files", []),
                expected_outputs=item.get("expected_outputs", []),
                output_files=[
                    item["output_file"]
                ] if "output_file" in item else [],
            )
        )

    return AgentResult(
        deliverables=deliverables,
        new_work_items=work_items,
        observations=[],
    )