from core.resources.agents.business_analyst_agent import BusinessAnalystAgent
from core.resources.agents.developer_agent import DeveloperAgent
from core.resources.agents.planning_agent import PlanningAgent
from core.agent_type import AgentType
from core.resources.agents.reviewer_agent import ReviewerAgent

class AgentRegistry:

    def __init__(self):

        self._agents = {
            AgentType.PLANNING: PlanningAgent(),
            AgentType.BUSINESS_ANALYST: BusinessAnalystAgent(),
            AgentType.DEVELOPER: DeveloperAgent(),
            AgentType.REVIEWER: ReviewerAgent(),
        }

    def get(self, agent_type):

        return self._agents[agent_type]
