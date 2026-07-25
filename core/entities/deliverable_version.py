from dataclasses import dataclass
from datetime import datetime
from core.agent_type import AgentType


@dataclass
class DeliverableVersion:
    version: int
    filename: str
    created_by: AgentType
    created_at: datetime
    review_score: float = 0.0
    review_summary: str = ""