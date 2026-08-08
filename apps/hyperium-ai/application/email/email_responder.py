from __future__ import annotations

from core.email.email_message import EmailMessage
from core.interfaces.llm_provider import LLMProvider

_SYSTEM = (
    "You are drafting a reply to a business email on behalf of the owner, as a "
    "capable employee would. Write only the body of the reply — no subject, no "
    "headers, no commentary. Be warm, clear and professional, match the sender's "
    "language, and keep it concise. Use what you know about the business. Sign "
    "off exactly as the business memory tells you to, and never leave a name or "
    "signature placeholder such as [Your Name] — if a sign-off is given, use it "
    "verbatim; if none is given, end simply with 'Best regards' and no name. For "
    "a genuinely unknown fact such as a date or price, do not invent it — leave a "
    "clearly marked placeholder like [confirm date]. This is a draft the owner "
    "reviews before sending."
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
