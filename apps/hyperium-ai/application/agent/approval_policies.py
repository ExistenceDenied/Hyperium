from __future__ import annotations

from core.agents.approval import ActionRequest, ApprovalDecision
from core.interfaces.approver import Approver


class AutoDenyApprover(Approver):
    """
    Refuses every side effect.

    The safe default. An unattended run stays read-only unless a human is
    present to approve, or approval has been delegated deliberately. Denial is
    fed back to the model, which can then find a route that does not act.
    """

    def review(self, request: ActionRequest) -> ApprovalDecision:
        return ApprovalDecision.deny(
            "no approver is available; side effects are refused by default"
        )


class AutoApproveApprover(Approver):
    """
    Approves every side effect.

    For trusted, unattended runs only. It removes the human from the loop, so
    it must be opted into deliberately — never the default.
    """

    def review(self, request: ActionRequest) -> ApprovalDecision:
        return ApprovalDecision.allow("auto-approved")
