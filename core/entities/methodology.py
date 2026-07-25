from dataclasses import dataclass


@dataclass
class Methodology:

    name: str

    description: str

    version: str = "1.0"