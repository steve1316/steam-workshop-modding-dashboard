"""Ollama provider for a local Ollama instance via its native /api/chat endpoint. No API key or cost."""

import json

import requests

from backend.core.settings import settings
from backend.providers.local_llm_provider import LocalLLMProvider, StreamChunk


class OllamaProvider(LocalLLMProvider):
    """Translation provider using a local Ollama instance."""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        """Initialize the Ollama provider.

        Args:
            base_url: Server base URL, defaulting to the config value.
            model: Model name, defaulting to the config value.
        """
        super().__init__(base_url or settings.ollama_base_url, model or settings.ollama_model)

    @property
    def name(self) -> str:
        return f"Ollama ({self._model})"

    @property
    def _server_name(self) -> str:
        return "Ollama"

    @property
    def _name_prefix(self) -> str:
        return "Ollama"

    @property
    def _endpoint(self) -> str:
        return "/api/chat"

    def _payload(self, system_prompt: str, user_message: str, num_entries: int, *, stream: bool) -> dict:
        # Ollama defaults to a small num_ctx (2048-4096) that silently truncates the prompt for large batches.
        prompt_chars = len(system_prompt) + len(user_message)
        estimated_tokens = int(prompt_chars / 3) + 8192  # headroom for output
        num_ctx = max(8192, ((estimated_tokens + 1023) // 1024) * 1024)
        return {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "options": {
                "num_ctx": num_ctx,
                "temperature": 0.3,
                "num_predict": 8192,
            },
            "stream": stream,
        }

    def _read_response(self, data: dict) -> tuple[str, int | None, int | None]:
        return data.get("message", {}).get("content", ""), data.get("prompt_eval_count"), data.get("eval_count")

    def _read_stream_line(self, line: str) -> StreamChunk:
        try:
            chunk = json.loads(line)
        except json.JSONDecodeError:
            return StreamChunk()
        if chunk.get("done"):
            return StreamChunk(done=True, usage=(chunk.get("prompt_eval_count"), chunk.get("eval_count")))
        return StreamChunk(token=chunk.get("message", {}).get("content", ""))

    def _free_gpu(self) -> None:
        """Tell Ollama to unload the model from GPU memory immediately."""
        try:
            requests.post(
                f"{self._base_url}/api/chat",
                json={"model": self._model, "messages": [], "keep_alive": 0},
                timeout=5,
            )
        except Exception:
            pass
