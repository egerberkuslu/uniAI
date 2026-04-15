"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self, system_prompt: str, user_message: str, max_tokens: int = 512
    ) -> str:
        """Generate a text completion given system + user prompts."""

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the identifier of the underlying model."""
