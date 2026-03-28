"""CodeRankEmbed embedding client wrapper using local inference."""

from sentence_transformers import SentenceTransformer


class CodeRankEmbedder:
    """Wrapper around CodeRankEmbed for code embeddings via sentence-transformers."""

    MODEL = "nomic-ai/CodeRankEmbed"

    QUERY_PREFIX = "Represent this query for searching relevant code: "

    def __init__(self) -> None:
        self._model = SentenceTransformer(self.MODEL, trust_remote_code=True)

    def _prepare(self, text: str, input_type: str) -> str:
        """Prepend the query prefix when input_type is 'query'."""
        if input_type == "query":
            return f"{self.QUERY_PREFIX}{text}"
        return text

    def embed(self, text: str, input_type: str = "document") -> list[float]:
        """Embed a single text string.

        Args:
            text: The text to embed.
            input_type: Either "document" or "query".

        Returns:
            A 768-dimensional embedding vector.
        """
        prepared = self._prepare(text, input_type)
        result = self._model.encode(prepared)
        return [float(x) for x in result]

    def embed_batch(
        self, texts: list[str], input_type: str = "document"
    ) -> list[list[float]]:
        """Embed a batch of text strings.

        Args:
            texts: The texts to embed.
            input_type: Either "document" or "query".

        Returns:
            A list of 768-dimensional embedding vectors.
        """
        if not texts:
            return []
        prepared = [self._prepare(t, input_type) for t in texts]
        results = self._model.encode(prepared)
        return [[float(x) for x in row] for row in results]
