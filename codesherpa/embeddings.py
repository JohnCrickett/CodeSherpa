"""Nomic embedding client wrapper using local inference."""

from sentence_transformers import SentenceTransformer


class NomicEmbedder:
    """Wrapper around nomic-embed-code for code embeddings via sentence-transformers."""

    MODEL = "nomic-ai/nomic-embed-code"

    PROMPT_NAMES = {
        "document": "search_document",
        "query": "search_query",
    }

    def __init__(self) -> None:
        self._model = SentenceTransformer(self.MODEL, trust_remote_code=True)

    def embed(self, text: str, input_type: str = "document") -> list[float]:
        """Embed a single text string.

        Args:
            text: The text to embed.
            input_type: Either "document" or "query".

        Returns:
            A 768-dimensional embedding vector.
        """
        prompt_name = self.PROMPT_NAMES[input_type]
        result = self._model.encode(text, prompt_name=prompt_name)
        return list(result)
