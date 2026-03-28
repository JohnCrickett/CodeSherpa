"""Tests for the Nomic embedding client wrapper."""


from codesherpa.embeddings import NomicEmbedder


class TestNomicEmbedder:
    """Tests for the NomicEmbedder wrapper."""

    def test_embed_returns_768_dim_vector(self, mocker):
        """Embedding a text returns a 768-dimensional vector."""
        mock_model_cls = mocker.patch("codesherpa.embeddings.SentenceTransformer")
        mock_model = mock_model_cls.return_value
        mock_model.encode.return_value = [0.1] * 768

        embedder = NomicEmbedder()
        result = embedder.embed("def hello(): pass")

        assert len(result) == 768
        mock_model_cls.assert_called_once_with(
            "nomic-ai/nomic-embed-code", trust_remote_code=True
        )
        mock_model.encode.assert_called_once_with(
            "def hello(): pass", prompt_name="search_document"
        )

    def test_embed_query_uses_search_query_prompt(self, mocker):
        """Embedding a query uses prompt_name='search_query'."""
        mock_model_cls = mocker.patch("codesherpa.embeddings.SentenceTransformer")
        mock_model = mock_model_cls.return_value
        mock_model.encode.return_value = [0.2] * 768

        embedder = NomicEmbedder()
        result = embedder.embed("what does this function do?", input_type="query")

        assert len(result) == 768
        mock_model.encode.assert_called_once_with(
            "what does this function do?", prompt_name="search_query"
        )

    def test_model_loaded_once(self, mocker):
        """Model is only instantiated once across multiple embed calls."""
        mock_model_cls = mocker.patch("codesherpa.embeddings.SentenceTransformer")
        mock_model = mock_model_cls.return_value
        mock_model.encode.return_value = [0.1] * 768

        embedder = NomicEmbedder()
        embedder.embed("text one")
        embedder.embed("text two")

        mock_model_cls.assert_called_once()
