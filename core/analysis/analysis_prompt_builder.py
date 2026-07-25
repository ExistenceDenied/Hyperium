from core.missions.mission import Mission


class AnalysisPromptBuilder:
    """
    Builds the prompt used to analyse a mission.
    """

    def build(self, mission: Mission) -> str:
        return f"""
You are an experienced management consultant.

Analyse the following mission.

Title:
{mission.title}

Objective:
{mission.objective}

Produce:

- Executive summary
- Assumptions
- Risks
- Recommended deliverables
"""