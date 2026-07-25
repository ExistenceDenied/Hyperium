import json

from core.planning_validator import validate_planning
from core.planning_mapper import map_planning


def parse_agent_result(text: str):

    try:
        data = json.loads(text)

    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON returned by agent:\n{text}"
        ) from e

    validate_planning(data)

    return map_planning(data)