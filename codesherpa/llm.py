"""LLM client wrapper using LangChain with Google Gemini."""

from langchain_google_genai import ChatGoogleGenerativeAI


def get_llm(api_key: str, model: str) -> ChatGoogleGenerativeAI:
    """Create a LangChain ChatGoogleGenerativeAI instance.

    Args:
        api_key: Google API key.
        model: Model name (e.g. gemini-2.5-flash).

    Returns:
        A configured ChatGoogleGenerativeAI instance.
    """
    return ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model=model,
    )
