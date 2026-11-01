"""llama.cpp provider for a local llama-server via its OpenAI-compatible /v1/chat/completions endpoint. No API key or cost."""

import json

from backend.core.settings import settings
from backend.providers.local_llm_provider import LocalLLMProvider, StreamChunk


class LlamaCppProvider(LocalLLMProvider):
    """Translation provider using a local llama-server instance. The model name is display-only because llama-server ignores it."""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        """Initialize the llama.cpp provider.

        Args:
            base_url: Server base URL, defaulting to the config value.
            model: Display-only model name, defaulting to the config value.
        """
        super().__init__(base_url or settings.llamacpp_base_url, model or settings.llamacpp_model)

    @property
    def name(self) -> str:
        label = self._model or "default"
        return f"llama.cpp ({label})"

    @property
    def _server_name(self) -> str:
        return "llama-server"

    @property
    def _name_prefix(self) -> str:
        return "llama.cpp"

    @property
    def _endpoint(self) -> str:
        return "/v1/chat/completions"

    @property
    def _model_label(self) -> str:
        return self._model or "llama.cpp"

    def _payload(self, system_prompt: str, user_message: str, num_entries: int, *, stream: bool) -> dict:
        # ~100 output tokens per entry for translations plus suggestions.
        estimated_output = max(8192, num_entries * 100 + 2048)
        return {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.3,
            "max_tokens": estimated_output,
            "stream": stream,
        }

    def _read_response(self, data: dict) -> tuple[str, int | None, int | None]:
        usage = data.get("usage", {})
        return data["choices"][0]["message"]["content"], usage.get("prompt_tokens"), usage.get("completion_tokens")

    def _read_stream_line(self, line: str) -> StreamChunk:
        # SSE lines look like "data: {...}" or "data: [DONE]".
        if not line.startswith("data: "):
            return StreamChunk()
        data_str = line[6:]
        if data_str.strip() == "[DONE]":
            return StreamChunk(done=True)
        try:
            chunk = json.loads(data_str)
        except json.JSONDecodeError:
            return StreamChunk()
        return StreamChunk(token=chunk.get("choices", [{}])[0].get("delta", {}).get("content", ""))

    def _free_gpu(self) -> None:
        """Stop the managed llama-server process to free GPU memory."""
        from backend import process_manager

        if process_manager.is_managed("llamacpp"):
            process_manager.stop_process("llamacpp")
