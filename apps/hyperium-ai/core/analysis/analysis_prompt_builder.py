from core.missions.mission import Mission


class AnalysisPromptBuilder:
    """
    Builds the prompt used to analyse a mission.

    Since 2.0 the analysis no longer decomposes the mission into work. A
    methodology does that, deterministically. What is left is the judgement a
    model is genuinely good at: understanding the mission, naming assumptions
    and risks, and recommending which methodology fits.
    """

    def build(self, mission: Mission, methodologies: list | None = None) -> str:
        catalogue = "\n".join(
            f"            - {item.key}: {item.name} — {item.description}"
            for item in (methodologies or [])
        ) or "            - (none available)"

        keys = ", ".join(item.key for item in (methodologies or [])) or "none"

        criteria = "\n".join(
            f"            - {criterion.description}"
            for criterion in mission.success_criteria
        ) or "            - (none stated)"

        constraints = "\n".join(
            f"            - {constraint.description}"
            for constraint in mission.constraints
        ) or "            - (none stated)"

        return f"""
            You are Hyperium's Engagement Analyst.

            Your task is NOT to answer the mission, and NOT to plan the work.
            The work is determined by a methodology, not by you.

            Your task is to understand the mission and recommend which
            methodology fits it.

            Return ONLY valid JSON.

            Schema:

            {{
            "summary": "A short paragraph restating what this engagement must achieve.",
            "assumptions": ["..."],
            "risks": ["..."],
            "recommended_methodology": "one of: {keys}",
            "rationale": "One sentence on why that methodology fits."
            }}

            Rules:
            - "recommended_methodology" must be exactly one of the keys listed
              below. Do not invent one.
            - State assumptions that, if wrong, would change the engagement.
            - State risks that are specific to this mission, not generic ones.

            Available methodologies:
{catalogue}

            Mission title:
            {mission.title}

            Mission objective:
            {mission.objective.description}

            Success criteria:
{criteria}

            Constraints:
{constraints}
            """
