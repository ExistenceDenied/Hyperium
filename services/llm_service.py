import json

from ollama import chat

from core.models import Message


class LLMService:

    def __init__(self, model: str = "qwen3"):
        self.model = model

    def ask(self, prompt: str) -> str:
        return self._chat(prompt)

    def ask_json(self, prompt: str) -> dict:
        response = self._chat(
            prompt=prompt,
            format="json",
        )

        return json.loads(response)

    def _chat(
        self,
        prompt: str,
        format: str | None = None,
    ) -> str:

        messages = [
            Message(
                role="user",
                content=prompt,
            )
        ]

        kwargs = {}

        if format is not None:
            kwargs["format"] = format

        response = chat(
            model=self.model,
            messages=[
                {
                    "role": m.role,
                    "content": m.content,
                }
                for m in messages
            ],
            options={
                "temperature": 0,
                "num_predict": 4096,
            },
            **kwargs,
        )

        return response["message"]["content"]