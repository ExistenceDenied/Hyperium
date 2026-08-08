from __future__ import annotations

import sys

from core.agents.approval import ActionRequest, ApprovalDecision
from core.interfaces.approver import Approver


class ConsoleApprover(Approver):
    """
    Asks the operator at the terminal before any side effect.

    A denied action is not a failure: the reason is fed back to the model so it
    can choose another route. An empty answer is treated as 'no' — the safe
    default when a person is unsure, and the safe default when there is no
    terminal to answer at all.
    """

    def review(self, request: ActionRequest) -> ApprovalDecision:
        print(f"\nThe agent wants to: {request.preview}", file=sys.stderr)

        try:
            answer = input("Approve? [y/N] ").strip().lower()
        except EOFError:
            answer = ""

        if answer in ("y", "yes"):
            return ApprovalDecision.allow()

        return ApprovalDecision.deny("the operator declined")
