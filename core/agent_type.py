from enum import Enum


class AgentType(str, Enum):

    PLANNING = "Planning Agent"

    BUSINESS_ANALYST = "Business Analyst"

    ENTERPRISE_ARCHITECT = "Enterprise Architect"

    SOLUTION_ARCHITECT = "Solution Architect"

    DEVELOPER = "Developer"

    TESTER = "Tester"

    REVIEWER = "Reviewer"
