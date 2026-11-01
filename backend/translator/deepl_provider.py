"""DeepL provider. DeepL takes no custom prompts, so glossary enforcement relies on DeepL's own glossary feature."""

from backend import config
from backend.translator.base import TranslationProvider

_DEEPL_LANG_CODES = {
    "Chinese": "ZH",
    "Chinese-TW [zh-tw]": "ZH",
    "Korean": "KO",
    "Japanese": "JA",
    "English": "EN",
}

_DEEPL_TARGET_CODES = {
    "English": "EN-US",
    "Chinese": "ZH-HANS",
    "Korean": "KO",
    "Japanese": "JA",
}


class DeepLProvider(TranslationProvider):
    """Translation provider using the DeepL API, with no custom prompts or glossary term suggestions."""

    def __init__(self, api_key: str | None = None):
        """Initialize the DeepL provider.

        Args:
            api_key: DeepL API key, defaulting to the config value.
        """
        self._api_key = api_key or config.DEEPL_API_KEY

    @property
    def name(self) -> str:
        """Human-readable provider name."""
        return "DeepL"

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
        """Translate a batch of strings using DeepL, which ignores the prompt-related arguments.

        Args:
            entries: (key, source_text) tuples.
            source_lang: Source language name, e.g. "Korean".
            glossary_prompt: Ignored.
            game_context: Ignored.
            format_rules: Ignored.
            style_examples: Ignored.

        Returns:
            (key -> translated text, empty suggestions list).
        """
        import deepl

        if not self._api_key:
            raise ValueError("DeepL API key not set. Set SWMT_DEEPL_API_KEY env var.")

        translator = deepl.Translator(self._api_key)

        deepl_source = _DEEPL_LANG_CODES.get(source_lang, "ZH")
        deepl_target = _DEEPL_TARGET_CODES.get(target_lang, "EN-US")

        results = {}
        texts = [text for _, text in entries]
        keys = [key for key, _ in entries]

        try:
            # DeepL handles batching natively.
            translations = translator.translate_text(
                texts,
                source_lang=deepl_source,
                target_lang=deepl_target,
                preserve_formatting=True,
            )

            for key, translation in zip(keys, translations, strict=False):
                results[key] = translation.text

        except deepl.DeepLException as e:
            print(f"  DeepL API error: {e}")

        return results, []

    def estimate_cost(self, entries: list[tuple[str, str]], **kwargs) -> dict:
        """Estimate the cost of translating the given entries, since DeepL charges per character.

        Args:
            entries: (key, source_text) tuples.

        Returns:
            Cost estimation dict.
        """
        total_chars = sum(len(text) for _, text in entries)

        # DeepL Pro pricing: $25 per 1M characters (approximate).
        estimated_cost = total_chars / 1_000_000 * 25.0

        return {
            "estimated_characters": total_chars,
            "estimated_cost_usd": round(estimated_cost, 4),
            "note": f"Estimated for {len(entries)} strings ({total_chars} chars). DeepL does not support custom glossary prompts — consider creating a DeepL glossary separately for term consistency.",
        }
