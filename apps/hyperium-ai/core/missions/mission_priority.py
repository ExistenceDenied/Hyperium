from enum import IntEnum


class MissionPriority(IntEnum):
    """
    Backlog priority. Ordered so that a plain sort puts the most important
    mission first.
    """

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

    @classmethod
    def parse(cls, value: str) -> "MissionPriority":
        try:
            return cls[value.strip().upper()]
        except KeyError:
            valid = ", ".join(item.name.lower() for item in cls)
            raise ValueError(
                f"Unknown priority '{value}'. Valid values: {valid}."
            ) from None
