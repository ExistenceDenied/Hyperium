from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Technique:
    """
    A named way of performing work.

    A capability says *what* a resource can do; a technique says *how* the work
    is done. Techniques are the reusable consulting craft — stakeholder
    mapping, event storming, a fishbone analysis — and they are what a
    consultant recognises as their own practice inside Hyperium.

    `guidance` is layered onto the capability persona when an activity runs.
    """

    key: str
    name: str
    description: str = ""
    guidance: str = ""
    capabilities: frozenset[str] = field(default_factory=frozenset)

    def applies_to(self, capability_key: str) -> bool:
        if not self.capabilities:
            return True

        return capability_key.strip().upper() in self.capabilities
