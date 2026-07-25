from enum import IntEnum


class ProficiencyLevel(IntEnum):
    """
    Defines the proficiency required or provided for a capability.
    """

    AWARENESS = 1
    BASIC = 2
    INTERMEDIATE = 3
    ADVANCED = 4
    EXPERT = 5