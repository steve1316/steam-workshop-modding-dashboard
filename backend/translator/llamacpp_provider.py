"""llama.cpp provider for a local llama-server via its OpenAI-compatible /v1/chat/completions endpoint. No API key or cost."""

import json
import time
from collections.abc import Generator
from threading import Event

import requests

from backend import config
from backend.translator.base import TranslationProvider


class LlamaCppProvider(TranslationProvider):
    """Translation provider using a local llama-server instance. The model name is display-only because llama-server ignores it."""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        """Initialize the llama.cpp provider.

        Args:
            base_url: Server base URL, defaulting to the config value.
            model: Display-only model name, defaulting to the config value.
        """
        self._base_url = base_url or config.LLAMACPP_BASE_URL
        self._model = model or config.LLAMACPP_MODEL

    def _stop_server(self) -> None:
        """Stop the managed llama-server process to free GPU memory."""
        from backend import process_manager

        if process_manager.is_managed("llamacpp"):
            process_manager.stop_process("llamacpp")

    @property
    def name(self) -> str:
        label = self._model or "default"
        return f"llama.cpp ({label})"

    @property
    def supports_streaming(self) -> bool:
        return True

    def translate_batch(
        self,
        entries: list[tuple[str, str]],
        source_lang: str,
        glossary_prompt: str,
        game_context: str = "",
        format_rules: list[str] | None = None,
        style_examples: dict[str, list[tuple[str, str]]] | None = None,
        character_context: dict | None = None,
        target_lang: str = "English",
    ) -> tuple[dict[str, str], list[dict]]:
        """Translate a batch of strings via llama-server.

        Args:
            entries: (key, source_text) tuples.
            source_lang: Source language name, e.g. `"Korean"`.
            glossary_prompt: Formatted glossary context.
            game_context: Game description for the system prompt.
            format_rules: Game-specific formatting preservation rules.
            style_examples: Category -> [(source, english)] pairs.
            character_context: Character background dict.

        Returns:
            (key -> translated text, suggested_terms dicts).
        """
        system_prompt, user_message = self.build_prompt(
            entries,
            source_lang,
            glossary_prompt,
            game_context=game_context,
            format_rules=format_rules,
            style_examples=style_examples,
            character_context=character_context,
            target_lang=target_lang,
        )

        # ~100 output tokens per entry for translations plus suggestions.
        estimated_output = max(8192, len(entries) * 100 + 2048)

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.3,
            "max_tokens": estimated_output,
            "stream": False,
        }

        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    f"{self._base_url}/v1/chat/completions",
                    json=payload,
                    timeout=600,
                )
                resp.raise_for_status()
                resp.encoding = "utf-8"
                data = resp.json()

                raw_text = data["choices"][0]["message"]["content"]
                translations, suggestions = self._parse_response(raw_text, entries)

                usage = data.get("usage", {})
                in_tok = usage.get("prompt_tokens")
                out_tok = usage.get("completion_tokens")

                self.last_raw_responses = getattr(self, "last_raw_responses", [])
                self.last_raw_responses.append(
                    {
                        "batch_index": len(self.last_raw_responses),
                        "model": self._model,
                        "input_tokens": in_tok,
                        "output_tokens": out_tok,
                        "cost_usd": 0.0,
                        "raw_text": raw_text,
                    }
                )
                return translations, suggestions

            except requests.ConnectionError:
                raise RuntimeError(f"Cannot connect to llama-server at {self._base_url}. Is llama-server running?")
            except requests.HTTPError as e:
                if attempt == max_retries - 1:
                    print(f"  llama-server API error after {max_retries} retries: {e}")
                    return {}, []
                wait_time = 2**attempt * 2
                time.sleep(wait_time)

        return {}, []

    def translate_batch_stream(
        self,
        entries: list[tuple[str, str]],
        source_lang: str,
        glossary_prompt: str,
        game_context: str = "",
        format_rules: list[str] | None = None,
        style_examples: dict[str, list[tuple[str, str]]] | None = None,
        character_context: dict | None = None,
        cancel_event: Event | None = None,
        target_lang: str = "English",
    ) -> Generator[dict, None, None]:
        """Stream translation via llama-server's /v1/chat/completions endpoint.

        Yields `progress` events every 0.5 s, then one `complete` event. If `cancel_event` is set mid-stream the connection is closed and a
        `cancelled` event is yielded.

        Args:
            entries: (key, source_text) tuples.
            source_lang: Source language name, e.g. `"Korean"`.
            glossary_prompt: Formatted glossary context.
            game_context: Game description for the system prompt.
            format_rules: Game-specific formatting preservation rules.
            style_examples: Category -> [(source, english)] pairs.
            character_context: Character background dict.
            cancel_event: When set, aborts the request and closes the connection.

        Yields:
            Dicts with a `"type"` of `"started"`, `"progress"`, `"complete"`, `"cancelled"`, `"error"` or `"retry"`.
        """
        system_prompt, user_message = self.build_prompt(
            entries,
            source_lang,
            glossary_prompt,
            game_context=game_context,
            format_rules=format_rules,
            style_examples=style_examples,
            character_context=character_context,
            target_lang=target_lang,
        )

        estimated_output = max(8192, len(entries) * 100 + 2048)

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.3,
            "max_tokens": estimated_output,
            "stream": True,
        }

        yield {"type": "started", "model": self._model or "llama.cpp", "num_entries": len(entries)}

        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    f"{self._base_url}/v1/chat/completions",
                    json=payload,
                    timeout=600,
                    stream=True,
                )
                resp.raise_for_status()
                resp.encoding = "utf-8"

                accumulated_text = ""
                tokens_generated = 0
                start_time = time.time()
                last_progress_time = 0.0

                for line in resp.iter_lines(decode_unicode=True):
                    if cancel_event and cancel_event.is_set():
                        resp.close()
                        self._stop_server()
                        yield {"type": "cancelled"}
                        return

                    if not line:
                        continue

                    # SSE lines look like "data: {...}" or "data: [DONE]".
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        accumulated_text += token
                        tokens_generated += 1

                        now = time.time()
                        if now - last_progress_time >= 0.5:
                            elapsed = now - start_time
                            yield {
                                "type": "progress",
                                "tokens_generated": tokens_generated,
                                "elapsed_sec": round(elapsed, 1),
                                "tokens_per_sec": round(tokens_generated / elapsed, 1) if elapsed > 0 else 0,
                            }
                            last_progress_time = now

                translations, suggestions = self._parse_response(accumulated_text, entries)

                self.last_raw_responses = getattr(self, "last_raw_responses", [])
                self.last_raw_responses.append(
                    {
                        "batch_index": len(self.last_raw_responses),
                        "model": self._model,
                        "input_tokens": None,
                        "output_tokens": tokens_generated,
                        "cost_usd": 0.0,
                        "raw_text": accumulated_text,
                    }
                )

                yield {
                    "type": "complete",
                    "translations": translations,
                    "suggestions": suggestions,
                    "input_tokens": None,
                    "output_tokens": tokens_generated,
                }
                return

            except requests.ConnectionError:
                yield {
                    "type": "error",
                    "message": f"Cannot connect to llama-server at {self._base_url}. Is llama-server running?",
                }
                return
            except requests.HTTPError as e:
                if attempt == max_retries - 1:
                    yield {"type": "error", "message": f"llama-server API error after {max_retries} retries: {e}"}
                    return
                yield {"type": "retry", "attempt": attempt + 1, "max_retries": max_retries}
                time.sleep(2**attempt * 2)

        yield {"type": "error", "message": "Translation failed after all retries"}

    def estimate_cost(self, entries: list[tuple[str, str]], **kwargs) -> dict:
        """Return a zero-cost estimate for local llama.cpp inference.

        Args:
            entries: (key, source_text) tuples.
            **kwargs: Ignored.

        Returns:
            Dict with `estimated_cost_usd` of 0.0, `model` and `note`.
        """
        return {
            "estimated_cost_usd": 0.0,
            "model": self._model or "llama.cpp",
            "note": f"llama.cpp local inference — no API cost ({len(entries)} strings)",
        }
