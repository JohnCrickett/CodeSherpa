"""Memory-aware query routing using LangGraph.

Builds a state graph that:
1. Checks memory for relevant prior context
2. Routes to "build on prior context" or "full explanation" path
3. After response, updates memory with what was explored
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from codesherpa.explanation import ExplanationResult, _format_context, explain
from codesherpa.memory import (
    search_episodic_memory,
    search_semantic_memory,
    store_episodic_memory,
)
from codesherpa.retrieval import hybrid_search

logger = logging.getLogger(__name__)

CONTEXT_SYSTEM_PROMPT = """\
You are CodeSherpa, an AI assistant that explains code in plain language.

You have prior context from previous explorations of this codebase.
Build on that context rather than starting from scratch — reference what
was previously explored and explain how the current query relates to it.

Rules:
- Explain code clearly, citing specific file paths and function/class names.
- When explaining relationships between parts of the codebase, reference both sides.
- When multiple implementations of a concept exist, mention all of them and explain differences.
- Never speculate beyond what the retrieved code supports.
- If the code context is insufficient to fully answer, explicitly state what you cannot determine.
- Keep explanations concise and accurate."""


class QueryState(TypedDict):
    """State for the memory-aware query processing graph."""

    query: str
    project_id: int
    conn: Any
    embedder: Any
    llm: Any
    episodic_memories: list[dict]
    semantic_memories: list[dict]
    response: ExplanationResult | None
    explored_files: list[str]


def check_memory(state: QueryState) -> dict:
    """Check memory for relevant prior context."""
    episodic = search_episodic_memory(
        state["conn"], state["embedder"], state["query"],
        project_id=state["project_id"],
    )
    semantic = search_semantic_memory(
        state["conn"], state["embedder"], state["query"],
        project_id=state["project_id"],
    )

    return {
        "episodic_memories": episodic,
        "semantic_memories": semantic,
    }


def route_query(state: QueryState) -> str:
    """Route to context-aware or fresh explanation based on memory presence."""
    if state["episodic_memories"] or state["semantic_memories"]:
        return "explain_with_context"
    return "explain_fresh"


def _format_memory_context(
    episodic: list[dict], semantic: list[dict]
) -> str:
    """Format memory entries into context for the LLM."""
    parts = []

    if episodic:
        parts.append("Previously explored areas:")
        for mem in episodic:
            files = ", ".join(mem["file_paths"]) if mem["file_paths"] else "none"
            parts.append(f"- Query: {mem['query']}")
            parts.append(f"  Files: {files}")
            parts.append(f"  Summary: {mem['summary']}")

    if semantic:
        parts.append("\nProject context provided by developer:")
        for mem in semantic:
            parts.append(f"- {mem['content']}")

    return "\n".join(parts)


def explain_with_context(state: QueryState) -> dict:
    """Generate explanation building on prior context from memory."""
    chunks = hybrid_search(
        state["conn"], state["embedder"], state["query"],
        project_id=state["project_id"],
    )
    code_context = _format_context(chunks)
    memory_context = _format_memory_context(
        state["episodic_memories"], state["semantic_memories"],
    )

    messages = [
        SystemMessage(content=CONTEXT_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Memory context:\n{memory_context}\n\n"
                f"Retrieved code context:\n\n{code_context}\n\n"
                f"Question: {state['query']}"
            )
        ),
    ]

    response = state["llm"].invoke(messages)
    explored_files = [c.file_path for c in chunks]

    return {
        "response": ExplanationResult(
            explanation=response.content,
            sources=chunks,
        ),
        "explored_files": explored_files,
    }


def explain_fresh(state: QueryState) -> dict:
    """Generate a fresh explanation without prior context."""
    result = explain(
        state["conn"], state["embedder"], state["llm"],
        state["query"], project_id=state["project_id"],
    )
    explored_files = [s.file_path for s in result.sources]

    return {
        "response": result,
        "explored_files": explored_files,
    }


def update_memory(state: QueryState) -> dict:
    """Store what was explored as episodic memory."""
    if state["response"] is None:
        return {}

    summary = state["response"].explanation[:200]
    file_paths = list(dict.fromkeys(state["explored_files"]))

    store_episodic_memory(
        conn=state["conn"],
        embedder=state["embedder"],
        project_id=state["project_id"],
        query=state["query"],
        file_paths=file_paths,
        summary=summary,
    )

    return {}


def build_query_graph() -> Any:
    """Build and compile the memory-aware query processing graph.

    Graph structure:
        check_memory → route_query →
            explain_with_context → update_memory → END
            explain_fresh → update_memory → END
    """
    graph = StateGraph(QueryState)

    graph.add_node("check_memory", check_memory)
    graph.add_node("explain_with_context", explain_with_context)
    graph.add_node("explain_fresh", explain_fresh)
    graph.add_node("update_memory", update_memory)

    graph.set_entry_point("check_memory")
    graph.add_conditional_edges(
        "check_memory",
        route_query,
        {
            "explain_with_context": "explain_with_context",
            "explain_fresh": "explain_fresh",
        },
    )
    graph.add_edge("explain_with_context", "update_memory")
    graph.add_edge("explain_fresh", "update_memory")
    graph.add_edge("update_memory", END)

    return graph.compile()
