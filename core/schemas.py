from pydantic import BaseModel


class DeliverableSchema(BaseModel):
    name: str
    filename: str
    owner: str


class WorkItemSchema(BaseModel):
    title: str
    assigned_agent: str
    description: str | None = None
    input_files: list[str] = []
    output_file: str | None = None


class PlanningResultSchema(BaseModel):
    project: str
    deliverables: list[DeliverableSchema]
    tasks: list[WorkItemSchema]
