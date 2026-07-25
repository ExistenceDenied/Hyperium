from core.agent_type import AgentType


ROLE_MAPPING = {

    # Planning
    "Planning Agent": AgentType.PLANNING,

    # Business
    "Business Analyst": AgentType.BUSINESS_ANALYST,
    "Project Manager": AgentType.BUSINESS_ANALYST,

    # Architecture
    "Enterprise Architect": AgentType.ENTERPRISE_ARCHITECT,
    "Solution Architect": AgentType.SOLUTION_ARCHITECT,
    "System Architect": AgentType.SOLUTION_ARCHITECT,

    # UX (tijdelijk uitgevoerd door Business Analyst)
    "UI/UX Designer": AgentType.BUSINESS_ANALYST,
    "UX Designer": AgentType.BUSINESS_ANALYST,

    # Development
    "Developer": AgentType.DEVELOPER,
    "Developers": AgentType.DEVELOPER,
    "Lead Developer": AgentType.DEVELOPER,
    "Software Engineer": AgentType.DEVELOPER,

    # Testing
    "Tester": AgentType.TESTER,
    "QA": AgentType.TESTER,
    "QA Engineer": AgentType.TESTER,
    "Quality Assurance": AgentType.TESTER,

    # Review
    "Reviewer": AgentType.REVIEWER,
}


def map_role(role: str) -> AgentType:

    try:
        return ROLE_MAPPING[role]
    except KeyError:
        supported = ", ".join(sorted(ROLE_MAPPING.keys()))
        raise ValueError(
            f"Unknown role '{role}'. Supported roles are: {supported}"
        )