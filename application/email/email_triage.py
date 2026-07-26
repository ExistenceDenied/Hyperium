from __future__ import annotations

import json
import logging
import re

from core.email.email_message import EmailMessage
from core.email.triage import CATEGORIES, TriageDecision
from core.interfaces.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_JSON = re.compile(r"\{.*\}", re.DOTALL)

_METHOD = """\
You triage a business email as an efficient assistant would. Decide the single \
best action, and separately what work the business must do as a result.

Choose exactly one category:
- "reply": it needs a written response — a question, an enquiry, or a request to \
produce or send something. Most requests are replies.
- "escalate": it truly needs the owner personally — a complaint, a legal or \
financial dispute, a sensitive negotiation, or a decision only they can make. Do \
NOT escalate a routine request to prepare a document, template, deck or report; \
that is a "reply" with a task. Escalate only when human judgement is really \
required.
- "fyi": informational, no response needed but worth the owner knowing.
- "skip": newsletters, marketing, receipts, automated notifications — noise.

Then list the concrete tasks the business should carry out. Crucially: if the \
email asks you to produce, prepare, create, draft or send any artifact — a \
document, template, presentation or deck, report, proposal, spreadsheet, \
analysis or plan — that is ALWAYS a task, phrased imperatively as producing a \
file, e.g. "Produce a test strategy template as a Word document and save it." \
Other real jobs (update a record, research something, follow up) are tasks too. \
Replying itself is NOT a task. If nothing real is warranted, return an empty \
list — never invent busywork.

Also give a one-line summary, a priority (low|medium|high) and your confidence \
(0 to 1)."""


class EmailTriage:
    """
    Classifies an email into an action and the work it implies.

    This is the methodology made executable: an email in, a decision out —
    category, priority, confidence, and a list of tasks the business should do.
    It uses business memory so the judgement reflects what matters to the owner,
    and it is told to escalate rather than guess when unsure.
    """

    def __init__(self, llm: LLMProvider, task_limit: int = 3) -> None:
        self._llm = llm
        self._task_limit = task_limit

    def classify(self, message: EmailMessage, context: str = "") -> TriageDecision:
        try:
            response = self._llm.generate(self._prompt(message, context))
        except Exception:
            logger.warning("Email triage call failed; escalating to be safe.")
            return TriageDecision(category="escalate", summary=message.subject)

        return self._parse(response, message)

    def _prompt(self, message: EmailMessage, context: str) -> str:
        parts = [_METHOD]
        if context:
            parts.append(context)
        parts.append(
            "# The email\n"
            f"From: {message.sender}\n"
            f"Subject: {message.subject}\n\n"
            f"{message.body[:3000]}"
        )
        parts.append(
            "Respond with a single JSON object and nothing else:\n"
            '{"category": "reply|escalate|fyi|skip", "priority": "low|medium|high",'
            ' "confidence": 0.0, "summary": "one line", "reason": "why",'
            ' "tasks": ["task the business should do", "..."]}'
        )
        return "\n\n".join(parts)

    def _parse(self, response: str, message: EmailMessage) -> TriageDecision:
        text = _THINK.sub("", response or "").strip()
        match = _JSON.search(text)
        if match is None:
            return TriageDecision(category="escalate", summary=message.subject)

        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return TriageDecision(category="escalate", summary=message.subject)

        category = str(data.get("category", "fyi")).strip().lower()
        if category not in CATEGORIES:
            category = "escalate"  # an unknown label means someone should look

        priority = str(data.get("priority", "medium")).strip().lower()
        if priority not in ("low", "medium", "high"):
            priority = "medium"

        tasks = data.get("tasks", [])
        if not isinstance(tasks, list):
            tasks = []
        tasks = [str(t).strip() for t in tasks if str(t).strip()][: self._task_limit]

        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

        return TriageDecision(
            category=category,
            priority=priority,
            confidence=confidence,
            summary=str(data.get("summary", "") or message.subject).strip(),
            reason=str(data.get("reason", "")).strip(),
            tasks=tasks,
        )
