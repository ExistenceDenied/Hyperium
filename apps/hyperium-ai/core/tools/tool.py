from __future__ import annotations

from abc import ABC, abstractmethod


class Tool(ABC):
    """
    A capability the agent can invoke while working on a task.

    A tool is the seam between the model and the world: the model decides to
    call one, Hyperium executes it, and the result is fed back into the loop.
    Concrete tools live in the infrastructure layer, because acting on the
    world — reading a file, fetching a URL — is exactly the kind of side effect
    the domain must not depend on.
    """

    #: Stable identifier the model calls. Must be a valid function name.
    name: str

    #: One sentence telling the model when to reach for this tool.
    description: str

    #: JSON Schema (an object schema) describing the tool's arguments.
    parameters: dict

    #: Whether invoking this changes the world and must be approved first.
    #: Read-only tools leave it False; anything that writes, sends, deletes or
    #: runs sets it True and passes through the approval gate.
    requires_approval: bool = False

    def preview(self, arguments: dict) -> str:
        """
        A human-readable description of what invoking this would do.

        Shown to the approver before a side-effecting tool runs, so the person
        deciding sees the concrete effect — 'Overwrite report.md (2 KB)' — not
        a raw argument dict. Side-effecting tools should override this.
        """
        return f"{self.name}({arguments})"

    @abstractmethod
    def invoke(self, arguments: dict) -> str:
        """
        Execute the tool and return a textual result for the model.

        Ordinary failure — a missing file, an unreachable URL — must be
        returned as an error string the model can read and recover from, not
        raised. Only genuinely exceptional conditions should propagate.
        """
        raise NotImplementedError

    def schema(self) -> dict:
        """The tool advertised in the provider's function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
