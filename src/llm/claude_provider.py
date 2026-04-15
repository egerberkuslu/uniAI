"""Claude (Anthropic) LLM provider."""

from __future__ import annotations

import anthropic

from src.config import AppConfig
from src.llm.base import LLMProvider


class ClaudeProvider(LLMProvider):
    def __init__(self, config: AppConfig) -> None:
        self._model = config.claude_model
        self._client = anthropic.Anthropic()

    def generate(
        self, system_prompt: str, user_message: str, max_tokens: int = 512
    ) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text

    def get_model_name(self) -> str:
        return self._model
