from __future__ import annotations

from abc import ABC, abstractmethod

from core.agents.approval import ActionRequest, ApprovalDecision


class Approver(ABC):
    """
    Decides whether a side-effecting tool call may run.

    The agent may observe the world on its own authority — read a file, fetch a
    URL. The moment it wants to change something (write a file, send a message,
    run a command) the decision passes here, so that acting on the user's
    systems is a human choice, not a model one.

    This is the same human-oversight principle the deliverable approval gate
    enforces, moved down to the level of a single action.
    """

    @abstractmethod
    def review(self, request: ActionRequest) -> ApprovalDecision:
        raise NotImplementedError
