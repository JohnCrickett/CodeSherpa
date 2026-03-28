"""Tests for the LLM client wrapper."""


from codesherpa.llm import get_llm


class TestGetLLM:
    """Tests for the LLM client factory."""

    def test_returns_langchain_gemini_model(self, mocker):
        """get_llm returns a LangChain ChatGoogleGenerativeAI instance."""
        mock_chat_cls = mocker.patch("codesherpa.llm.ChatGoogleGenerativeAI")

        llm = get_llm(api_key="test-key", model="gemini-2.5-flash")

        mock_chat_cls.assert_called_once_with(
            google_api_key="test-key",
            model="gemini-2.5-flash",
        )
        assert llm is mock_chat_cls.return_value
