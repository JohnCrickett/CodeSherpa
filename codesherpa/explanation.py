"""LLM-powered code explanations using LangChain retrieval chains."""

from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from codesherpa.embeddings import CodeRankEmbedder
from codesherpa.retrieval import SearchResult, hybrid_search

SYSTEM_PROMPT = """\
You are CodeSherpa, an AI assistant that explains code in plain language.

Rules:
- Explain code clearly, citing specific file paths and function/class names.
- When explaining relationships between parts of the codebase, reference both sides.
- When multiple implementations of a concept exist, mention all of them and explain differences.
- Never speculate beyond what the retrieved code supports.
- If the code context is insufficient to fully answer, explicitly state what you cannot determine.
- Keep explanations concise and accurate."""


def _format_context(chunks: list[SearchResult]) -> str:
    """Format retrieved code chunks into a context string for the LLM."""
    if not chunks:
        return "No relevant code was found in the codebase."

    parts = []
    for chunk in chunks:
        parts.append(
            f"File: {chunk.file_path} ({chunk.chunk_type})\n"
            f"```\n{chunk.code_text}\n```"
        )
    return "\n\n".join(parts)


@dataclass
class ExplanationResult:
    """An LLM-generated explanation with source code references."""

    explanation: str
    sources: list[SearchResult]


def explain(
    conn,
    embedder: CodeRankEmbedder,
    llm,
    question: str,
    top_k: int = 10,
    project_id: int | None = None,
) -> ExplanationResult:
    """Retrieve relevant code and generate a plain-language explanation.

    Args:
        conn: Oracle Database connection.
        embedder: Embedding client for query encoding.
        llm: LangChain LLM instance.
        question: The user's natural language question.
        top_k: Maximum number of code chunks to retrieve.
        project_id: If provided, restrict search to this project.

    Returns:
        ExplanationResult with the explanation text and source chunks.
    """
    chunks = hybrid_search(conn, embedder, question, top_k=top_k, project_id=project_id)
    context = _format_context(chunks)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=f"Retrieved code context:\n\n{context}\n\nQuestion: {question}"
        ),
    ]

    response = llm.invoke(messages)

    return ExplanationResult(
        explanation=response.content,
        sources=chunks,
    )
