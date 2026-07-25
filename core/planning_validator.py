REQUIRED_DELIVERABLE_FIELDS = {
    "name",
    "filename",
    "owner",
}

REQUIRED_TASK_FIELDS = {
    "title",
    "assigned_agent",
    "expected_outputs",
}


def validate_planning(data: dict):

    if "deliverables" not in data:
        raise ValueError("Planning JSON has no 'deliverables'.")

    if "tasks" not in data:
        raise ValueError("Planning JSON has no 'tasks'.")

    for i, deliverable in enumerate(data["deliverables"]):

        missing = REQUIRED_DELIVERABLE_FIELDS - deliverable.keys()

        if missing:
            raise ValueError(
                f"Deliverable {i} is missing fields: {missing}"
            )

    for i, task in enumerate(data["tasks"]):

        missing = REQUIRED_TASK_FIELDS - task.keys()

        if missing:
            raise ValueError(
                f"Task {i} is missing fields: {missing}"
            )