"""Shared request, retry and streaming flow for local LLM servers (Ollama, llama.cpp). No API key or cost."""

import time
from abc import abstractmethod
from collections.abc import Generator
from dataclasses import dataclass
from threading import Event

import requests

from backend.providers.base import TranslationProvider


@dataclass(frozen=True)
class StreamChunk:
    """One parsed line of a streamed chat response.

    Attributes:
        token: Generated text in this line, empty for keep-alives and metadata.
        done: Whether the server signalled the end of the stream.
        usage: `(input_tokens, output_tokens)` when the server reported them.
    """

    token: str = ""
    done: bool = False
    usage: tuple[int | None, int | None] | None = None


class LocalLLMProvider(TranslationProvider):
    """Base for providers that talk to a local chat server, leaving the endpoint, payload and response shapes to each subclass."""

    _MAX_RETRIES = 3

    def __init__(self, base_url: str, model: str):
        """Initialize the provider.

        Args:
            base_url: Server base URL.
            model: Model name.
        """
        self._base_url = base_url
        self._model = model

    @property
    def supports_streaming(self) -> bool:
        return True

    @property
    @abstractmethod
    def _server_name(self) -> str:
        """Server name used in connection errors, e.g. `"Ollama"`."""

    @property
    @abstractmethod
    def _endpoint(self) -> str:
        """Chat endpoint path, e.g. `"/api/chat"`."""

    @property
    @abstractmethod
    def _name_prefix(self) -> str:
        """Short provider label used in names and estimate notes, e.g. `"llama.cpp"`."""

    @property
    def _model_label(self) -> str:
        """Model name recorded in logs and estimates."""
        return self._model

    @abstractmethod
    def _payload(self, system_prompt: str, user_message: str, num_entries: int, *, stream: bool) -> dict:
        """Build the request body.

        Args:
            system_prompt: Built system prompt.
            user_message: Built user message.
            num_entries: Batch size, used to size the output budget.
            stream: Whether to request a streamed response.

        Returns:
            JSON request body.
        """

    @abstractmethod
    def _read_response(self, data: dict) -> tuple[str, int | None, int | None]:
        """Pull the text and token counts out of a non-streamed response.

        Args:
            data: Parsed response JSON.

        Returns:
            `(raw_text, input_tokens, output_tokens)`.
        """

    @abstractmethod
    def _read_stream_line(self, line: str) -> StreamChunk:
        """Parse one non-empty line of a streamed response.

        Args:
            line: Decoded response line.

        Returns:
            The parsed chunk, empty when the line carries no token.
        """

    @abstractmethod
    def _free_gpu(self) -> None:
        """Release GPU memory after a cancelled stream."""

    def _connect_error(self) -> str:
        """Return the message shown when the server is unreachable."""
        return f"Cannot connect to {self._server_name} at {self._base_url}. Is {self._server_name} running?"

    def _record_raw(self, raw_text: str, input_tokens: int | None, output_tokens: int | None) -> None:
        """Append one call to `last_raw_responses` for the API-response log.

        Args:
            raw_text: Raw model output.
            input_tokens: Prompt token count, when reported.
            output_tokens: Completion token count, when reported.
        """
        self.last_raw_responses = getattr(self, "last_raw_responses", [])
        self.last_raw_responses.append(
            {
                "batch_index": len(self.last_raw_responses),
                "model": self._model_label,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": 0.0,
                "raw_text": raw_text,
            }
        )

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
        """Translate a batch of strings in one non-streamed request.

        Args:
            entries: (key, source_text) tuples.
            source_lang: Source language name, e.g. `"Korean"`.
            glossary_prompt: Formatted glossary context.
            game_context: Game description for the system prompt.
            format_rules: Game-specific formatting preservation rules.
            style_examples: Category -> [(source, english)] pairs.
            character_context: Character background dict.
            target_lang: Language to translate into.

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
        payload = self._payload(system_prompt, user_message, len(entries), stream=False)

        for attempt in range(self._MAX_RETRIES):
            try:
                resp = requests.post(f"{self._base_url}{self._endpoint}", json=payload, timeout=600)
                resp.raise_for_status()
                resp.encoding = "utf-8"
                raw_text, in_tok, out_tok = self._read_response(resp.json())
                translations, suggestions = self._parse_response(raw_text, entries)
                self._record_raw(raw_text, in_tok, out_tok)
                return translations, suggestions
            except requests.ConnectionError:
                raise RuntimeError(self._connect_error()) from None
            except requests.HTTPError as e:
                if attempt == self._MAX_RETRIES - 1:
                    print(f"  {self._server_name} API error after {self._MAX_RETRIES} retries: {e}")
                    return {}, []
                time.sleep(2**attempt * 2)

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
        """Stream a batch translation.

        Yields `progress` events every 0.5 s, then one `complete` event. If `cancel_event` is set mid-stream the connection is closed, GPU memory
        is freed and a `cancelled` event is yielded.

        Args:
            entries: (key, source_text) tuples.
            source_lang: Source language name, e.g. `"Korean"`.
            glossary_prompt: Formatted glossary context.
            game_context: Game description for the system prompt.
            format_rules: Game-specific formatting preservation rules.
            style_examples: Category -> [(source, english)] pairs.
            character_context: Character background dict.
            cancel_event: When set, aborts the request and closes the connection.
            target_lang: Language to translate into.

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
        payload = self._payload(system_prompt, user_message, len(entries), stream=True)

        yield {"type": "started", "model": self._model_label, "num_entries": len(entries)}

        for attempt in range(self._MAX_RETRIES):
            try:
                resp = requests.post(f"{self._base_url}{self._endpoint}", json=payload, timeout=600, stream=True)
                resp.raise_for_status()
                resp.encoding = "utf-8"

                accumulated_text = ""
                tokens_generated = 0
                usage = None
                start_time = time.time()
                last_progress_time = 0.0

                for line in resp.iter_lines(decode_unicode=True):
                    if cancel_event and cancel_event.is_set():
                        resp.close()
                        self._free_gpu()
                        yield {"type": "cancelled"}
                        return

                    if not line:
                        continue
                    chunk = self._read_stream_line(line)
                    if chunk.usage is not None:
                        usage = chunk.usage
                    if chunk.done:
                        break
                    if not chunk.token:
                        continue

                    accumulated_text += chunk.token
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

                # Servers that report no usage still let the streamed token count stand in for output tokens.
                in_tok, out_tok = usage or (None, tokens_generated)
                translations, suggestions = self._parse_response(accumulated_text, entries)
                self._record_raw(accumulated_text, in_tok, out_tok)

                yield {
                    "type": "complete",
                    "translations": translations,
                    "suggestions": suggestions,
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                }
                return

            except requests.ConnectionError:
                yield {"type": "error", "message": self._connect_error()}
                return
            except requests.HTTPError as e:
                if attempt == self._MAX_RETRIES - 1:
                    yield {"type": "error", "message": f"{self._server_name} API error after {self._MAX_RETRIES} retries: {e}"}
                    return
                yield {"type": "retry", "attempt": attempt + 1, "max_retries": self._MAX_RETRIES}
                time.sleep(2**attempt * 2)

        yield {"type": "error", "message": "Translation failed after all retries"}

    def estimate_cost(self, entries: list[tuple[str, str]], **kwargs) -> dict:
        """Return a zero-cost estimate for local inference.

        Args:
            entries: (key, source_text) tuples.
            **kwargs: Ignored.

        Returns:
            Dict with `estimated_cost_usd` of 0.0, `model` and `note`.
        """
        return {
            "estimated_cost_usd": 0.0,
            "model": self._model_label,
            "note": f"{self._name_prefix} local inference — no API cost ({len(entries)} strings)",
        }
