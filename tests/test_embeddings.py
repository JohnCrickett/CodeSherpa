"""Tests for the CodeRankEmbed embedding client wrapper."""


from codesherpa.embeddings import CodeRankEmbedder


class TestCodeRankEmbedder:
    """Tests for the CodeRankEmbedder wrapper."""

    def test_embed_returns_768_dim_vector(self, mocker):
        """Embedding a text returns a 768-dimensional vector."""
        mock_model_cls = mocker.patch("codesherpa.embeddings.SentenceTransformer")
        mock_model = mock_model_cls.return_value
        mock_model.encode.return_value = [0.1] * 768

        embedder = CodeRankEmbedder()
        result = embedder.embed("def hello(): pass")

        assert len(result) == 768
        mock_model_cls.assert_called_once_with(
            "nomic-ai/CodeRankEmbed", trust_remote_code=True
        )
        mock_model.encode.assert_called_once_with("def hello(): pass")

    def test_embed_query_prepends_prefix(self, mocker):
        """Embedding a query prepends the CodeRankEmbed query prefix."""
        mock_model_cls = mocker.patch("codesherpa.embeddings.SentenceTransformer")
        mock_model = mock_model_cls.return_value
        mock_model.encode.return_value = [0.2] * 768

        embedder = CodeRankEmbedder()
        result = embedder.embed("what does this function do?", input_type="query")

        assert len(result) == 768
        mock_model.encode.assert_called_once_with(
            "Represent this query for searching relevant code: what does this function do?"
        )

    def test_embed_document_no_prefix(self, mocker):
        """Embedding a document does not prepend any prefix."""
        mock_model_cls = mocker.patch("codesherpa.embeddings.SentenceTransformer")
        mock_model = mock_model_cls.return_value
        mock_model.encode.return_value = [0.1] * 768

        embedder = CodeRankEmbedder()
        embedder.embed("def hello(): pass", input_type="document")

        mock_model.encode.assert_called_once_with("def hello(): pass")

    def test_model_loaded_once(self, mocker):
        """Model is only instantiated once across multiple embed calls."""
        mock_model_cls = mocker.patch("codesherpa.embeddings.SentenceTransformer")
        mock_model = mock_model_cls.return_value
        mock_model.encode.return_value = [0.1] * 768

        embedder = CodeRankEmbedder()
        embedder.embed("text one")
        embedder.embed("text two")

        mock_model_cls.assert_called_once()
