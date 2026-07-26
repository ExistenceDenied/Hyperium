from __future__ import annotations

from core.email.email_message import EmailMessage
from core.interfaces.llm_provider import LLMProvider

_SYSTEM = (
    "You are drafting a reply to a business email on behalf of the owner, as a "
    "capable employee would. Write only the body of the reply — no subject, no "
    "headers, no commentary. Be warm, clear and professional, match the sender's "
    "language, and keep it concise. Use what you know about the business; where a "
    "fact you would need is not available, do not invent it — leave a clearly "
    "marked placeholder like [confirm date] for the owner to fill in. This is a "
    "draft the owner will read before sending."
)


class EmailResponder:
    """
    Turns a received email into a draft reply, in the business's voice.

    It leans on business memory so the reply sounds like the business and gets
    its facts right, and it is told to flag anything it cannot know rather than
    guess — because a person sends the result, and a confident wrong answer is
    worse than an obvious gap.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def compose(self, message: EmailMessage, context: str = "") -> str:
        parts = [_SYSTEM]
        if context:
            parts.append(context)
        parts.append(
            "Reply to this email:\n"
            f"From: {message.sender}\n"
            f"Subject: {message.subject}\n\n"
            f"{message.body}"
        )
        return self._llm.generate("\n\n".join(parts)).strip()
