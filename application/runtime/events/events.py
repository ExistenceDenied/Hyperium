from enum import Enum


class RuntimeEvent(Enum):

    TASK_STARTED = "task_started"

    TASK_COMPLETED = "task_completed"

    TASK_FAILED = "task_failed"

    PROJECT_STARTED = "project_started"

    PROJECT_COMPLETED = "project_completed"
