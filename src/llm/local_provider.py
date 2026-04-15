"""Local LLM provider using HuggingFace transformers."""

from __future__ import annotations

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from src.config import AppConfig
from src.llm.base import LLMProvider


class LocalProvider(LLMProvider):
    """
    Uses a local model via the transformers library.

    CRITICAL implementation notes:
    - Uses apply_chat_template() for proper instruction formatting
    - Sets max_new_tokens (NOT max_length)
    - Sets pad_token = eos_token
    - Decodes only NEW tokens (output[prompt_length:])
    - Uses repetition_penalty=1.2 to prevent loops
    """

    def __init__(self, config: AppConfig) -> None:
        model_name = config.local_model_name
        self._model_name = model_name
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token
        self._model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None,
        )
        if not torch.cuda.is_available():
            self._model = self._model.to("cpu")
        self._model.eval()

    def generate(
        self, system_prompt: str, user_message: str, max_tokens: int = 512
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        prompt_text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(prompt_text, return_tensors="pt")
        input_ids = inputs["input_ids"]
        prompt_length = input_ids.shape[1]

        device = next(self._model.parameters()).device
        input_ids = input_ids.to(device)

        with torch.no_grad():
            output = self._model.generate(
                input_ids,
                max_new_tokens=max_tokens,
                repetition_penalty=1.2,
                do_sample=True,
                temperature=0.7,
                pad_token_id=self._tokenizer.eos_token_id,
            )

        new_tokens = output[0][prompt_length:]
        return self._tokenizer.decode(new_tokens, skip_special_tokens=True)

    def get_model_name(self) -> str:
        return self._model_name
