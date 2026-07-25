from core.agent_type import AgentType
from application.registry.agent_registry import AgentRegistry


def test_registry_returns_business_analyst():

    registry = AgentRegistry()

    agent = registry.get(AgentType.BUSINESS_ANALYST)

    assert agent is not None
