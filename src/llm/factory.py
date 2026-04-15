"""Factory for creating the appropriate LLM provider."""

from __future__ import annotations

from src.config import AppConfig
from src.llm.base import LLMProvider


class LLMProviderFactory:
    @staticmethod
    def create(config: AppConfig) -> LLMProvider:
        if config.use_claude_api:
            from src.llm.claude_provider import ClaudeProvider

            return ClaudeProvider(config)
        else:
            # Heuristic: if the local model looks like an Ollama tag (contains ':')
            # then use the Ollama provider; otherwise load via transformers.
            if ":" in (config.local_model_name or ""):
                from src.llm.ollama_provider import OllamaProvider

                return OllamaProvider(config)
            else:
                from src.llm.local_provider import LocalProvider

                return LocalProvider(config)
