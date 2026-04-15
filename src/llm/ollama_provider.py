"""Local LLM provider using a running Ollama server."""

from __future__ import annotations

import json
from urllib import request, error

from src.config import AppConfig
from src.llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    """
    Talks to a local Ollama instance via HTTP.
    Expects the model (e.g. "deepseek-r1:14b") to already be pulled locally.
    """

    def __init__(self, config: AppConfig) -> None:
        self._model = config.local_model_name
        self._base_url = config.ollama_host.rstrip("/")

    def generate(
        self, system_prompt: str, user_message: str, max_tokens: int = 512
    ) -> str:
        # Sanity check: ensure the model exists locally to provide a clear error.
        if not self._model_exists():
            raise RuntimeError(
                f"Ollama model '{self._model}' not found. Run: 'ollama pull {self._model}'"
            )
        url = f"{self._base_url}/api/chat"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "options": {
                # Align with our existing provider interface
                "num_predict": max_tokens,
                "temperature": 0.1,
            },
        }

        data = json.dumps(payload).encode("utf-8")
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"})

        try:
            with request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8")
                obj = json.loads(body)
        except error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else str(e)
            raise RuntimeError(f"Ollama HTTP error {e.code}: {detail}") from e
        except Exception as e:  # pragma: no cover - depends on runtime
            raise RuntimeError(f"Failed to call Ollama at {url}: {e}") from e

        # /api/chat returns { "message": { "content": "..." }, ... }
        message = obj.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            # Fallback for older/newer API shapes
            content = obj.get("response") or ""
        return content

    def get_model_name(self) -> str:
        return self._model

    def _model_exists(self) -> bool:
        try:
            url = f"{self._base_url}/api/tags"
            with request.urlopen(url, timeout=10) as resp:
                obj = json.loads(resp.read().decode("utf-8"))
            models = obj.get("models") or []
            # Each entry typically has a 'name' like 'deepseek-r1:14b'
            names = {m.get("name") for m in models if isinstance(m, dict)}
            return self._model in names
        except Exception:
            # If tag listing fails (older Ollama or network hiccup), don't block generation.
            return True
