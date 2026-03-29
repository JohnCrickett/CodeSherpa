"""Intelligent navigation: multi-step retrieval, follow-ups, exploration planning, and map query.

Builds a LangGraph state graph that classifies queries and routes them to
specialised handlers for map queries, follow-up questions, broad explorations,
and specific code questions with dependency linking.
"""

from __future__ import annotations

import logging
import re
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from codesherpa.explanation import ExplanationResult, _format_context
from codesherpa.ingestion import TABLE_NAME
from codesherpa.memory import (
    search_episodic_memory,
    search_semantic_memory,
    store_episodic_memory,
)
from codesherpa.retrieval import hybrid_search

logger = logging.getLogger(__name__)

# Follow-up indicator words that suggest a query builds on prior context
_FOLLOW_UP_INDICATORS = re.compile(
    r"\b(this|that|it|these|those|the same|above|previous|calls?\s+this|"
    r"where\s+is\s+(it|this|that)\s+used|who\s+calls|what\s+calls)\b",
    re.IGNORECASE,
)

NAVIGATION_SYSTEM_PROMPT = """\
You are CodeSherpa, an AI assistant that explains code in plain language.

Rules:
- Explain code clearly, citing specific file paths and function/class names.
- When explaining relationships between parts of the codebase, reference both sides.
- When multiple implementations of a concept exist, mention all of them and explain differences.
- Never speculate beyond what the retrieved code supports.
- If the code context is insufficient to fully answer, explicitly state what you cannot determine.
- Keep explanations concise and accurate.
- When you identify dependencies (imports, function calls, class inheritance), mention them
  explicitly so the user can explore further."""

CLASSIFY_PROMPT = """\
Classify the following user question about a codebase into exactly one category.
Reply with ONLY one word: "exploration" or "specific".

- "exploration": broad questions about how a system, feature, or flow works
  (e.g., "how does authentication work?", "explain the data pipeline")
- "specific": targeted questions about a particular function, class, or file
  (e.g., "what does parse_codebase do?", "explain the SearchResult class")

Question: {query}"""

MAP_SYSTEM_PROMPT = """\
You are CodeSherpa. Summarise the high-level structure of a codebase given the
metadata below. Include:
- Languages used (with approximate chunk counts)
- Top-level modules / directory structure
- Likely entry points (main files, CLI modules, app factories) where identifiable
Keep it concise and well-organised using Markdown."""

EXPLORATION_PLAN_PROMPT = """\
You are CodeSherpa. A user wants to understand a broad area of a codebase.
Given their question, produce a short numbered list (2-4 items) of specific
search queries that would help trace the flow. Each query should target a
specific function, class, or concept to retrieve.

Reply ONLY with the numbered list, no other text.

Question: {query}"""

EXPLORATION_SYNTHESISE_PROMPT = """\
You are CodeSherpa. Produce a coherent walkthrough of the codebase area
described below. Structure the explanation as a flow, connecting the pieces
logically rather than listing search results.

Rules:
- Cite specific file paths and function/class names.
- Explain how the pieces connect to each other.
- Keep it concise and accurate.
- Never speculate beyond what the code supports."""


class NavigationState(TypedDict):
    """State for the intelligent navigation graph."""

    query: str
    project_id: int
    conn: Any
    embedder: Any
    llm: Any
    conversation_history: list[dict]
    query_type: str
    response: ExplanationResult | None
    dependencies: list[dict]
    explored_files: list[str]
    episodic_memories: list[dict]
    semantic_memories: list[dict]


def check_memory(state: NavigationState) -> dict:
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


def classify_query(state: NavigationState) -> dict:
    """Classify the query into map, follow_up, exploration, or specific."""
    query = state["query"].strip()

    # Map query: exact match
    if query.lower() == "map":
        return {"query_type": "map"}

    # Follow-up: has conversation history and uses referential language
    if state["conversation_history"] and _FOLLOW_UP_INDICATORS.search(query):
        return {"query_type": "follow_up"}

    # Use LLM to distinguish exploration vs specific
    messages = [
        HumanMessage(content=CLASSIFY_PROMPT.format(query=query)),
    ]
    response = state["llm"].invoke(messages)
    classification = response.content.strip().lower()

    if "exploration" in classification:
        return {"query_type": "exploration"}
    return {"query_type": "specific"}


def route_by_type(state: NavigationState) -> str:
    """Route to the appropriate handler based on query_type."""
    qt = state["query_type"]
    if qt == "map":
        return "handle_map"
    if qt == "exploration":
        return "plan_exploration"
    # Both follow_up and specific use multi-step retrieval
    return "multi_step_retrieve"


def handle_map_query(state: NavigationState) -> dict:
    """Handle a 'map' query by summarising codebase structure from metadata."""
    conn = state["conn"]
    project_id = state["project_id"]

    with conn.cursor() as cursor:
        # Language breakdown
        cursor.execute(
            f"SELECT language, COUNT(*) AS cnt FROM {TABLE_NAME} "
            f"WHERE project_id = :1 GROUP BY language ORDER BY cnt DESC",
            [project_id],
        )
        lang_rows = cursor.fetchall()

        # File paths for module structure
        cursor.execute(
            f"SELECT DISTINCT file_path FROM {TABLE_NAME} "
            f"WHERE project_id = :1 ORDER BY file_path",
            [project_id],
        )
        file_rows = cursor.fetchall()

    # Build metadata summary for the LLM
    parts = []
    if lang_rows:
        parts.append("Languages:")
        for lang, count in lang_rows:
            parts.append(f"  - {lang}: {count} chunks")

    if file_rows:
        file_paths = [row[0] for row in file_rows]
        parts.append(f"\nFiles ({len(file_paths)} total):")
        for fp in file_paths:
            parts.append(f"  - {fp}")

    metadata_text = "\n".join(parts) if parts else "No data ingested yet."

    messages = [
        SystemMessage(content=MAP_SYSTEM_PROMPT),
        HumanMessage(content=f"Codebase metadata:\n{metadata_text}"),
    ]
    response = state["llm"].invoke(messages)

    return {
        "response": ExplanationResult(explanation=response.content, sources=[]),
        "explored_files": [],
    }


def extract_dependencies(chunks: list) -> list[dict]:
    """Extract dependency references (imports, calls, inheritance) from code chunks.

    Returns a list of dicts with keys: type, target, source_file.
    """
    deps: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for chunk in chunks:
        code = chunk.code_text
        file_path = chunk.file_path

        # Python imports: import X / from X import Y
        for match in re.finditer(
            r"^(?:from\s+([\w.]+)\s+import\s+[\w, ]+|import\s+([\w., ]+))",
            code,
            re.MULTILINE,
        ):
            target = match.group(1) or match.group(2)
            for t in target.split(","):
                t = t.strip()
                if t:
                    key = ("import", t)
                    if key not in seen:
                        seen.add(key)
                        deps.append({"type": "import", "target": t, "source_file": file_path})

        # Class inheritance: class X(Parent)
        for match in re.finditer(r"class\s+\w+\(([^)]+)\)", code):
            parents = match.group(1)
            for parent in parents.split(","):
                parent = parent.strip()
                if parent and parent not in ("object",):
                    key = ("inherits", parent)
                    if key not in seen:
                        seen.add(key)
                        deps.append({
                            "type": "inherits", "target": parent,
                            "source_file": file_path,
                        })

        # Function calls: name(...)
        # Exclude common keywords and builtins
        _SKIP_CALLS = {
            "if", "for", "while", "return", "print", "len", "range", "str",
            "int", "float", "list", "dict", "set", "tuple", "type", "isinstance",
            "hasattr", "getattr", "setattr", "super", "property", "staticmethod",
            "classmethod", "True", "False", "None", "not", "and", "or", "in",
            "class", "def", "import", "from", "as", "with", "assert", "raise",
            "except", "finally", "try", "yield", "pass", "break", "continue",
            "del", "global", "nonlocal", "lambda", "elif", "else",
        }
        for match in re.finditer(r"\b([a-zA-Z_]\w*)\s*\(", code):
            name = match.group(1)
            if name not in _SKIP_CALLS and not name[0].isupper():
                # Skip class constructors (UpperCase names) and builtins
                key = ("calls", name)
                if key not in seen:
                    seen.add(key)
                    deps.append({"type": "calls", "target": name, "source_file": file_path})

    return deps


def _format_memory_context(episodic: list[dict], semantic: list[dict]) -> str:
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


def _format_history_context(history: list[dict]) -> str:
    """Format conversation history into context for the LLM."""
    if not history:
        return ""
    parts = ["Conversation history:"]
    for entry in history[-3:]:  # Last 3 entries for context
        parts.append(f"- Q: {entry['query']}")
        if "summary" in entry:
            parts.append(f"  A: {entry['summary']}")
        if "files" in entry:
            parts.append(f"  Files: {', '.join(entry['files'])}")
    return "\n".join(parts)


def multi_step_retrieve(state: NavigationState) -> dict:
    """Multi-step retrieval: retrieve → extract references → retrieve again → explain.

    For follow-ups, includes conversation history as context.
    For specific queries, does initial retrieval plus dependency-aware follow-up.
    """
    conn = state["conn"]
    embedder = state["embedder"]
    llm = state["llm"]
    query = state["query"]
    project_id = state["project_id"]

    # Step 1: Initial retrieval
    # For follow-ups, augment query with history context
    search_query = query
    if state["query_type"] == "follow_up" and state["conversation_history"]:
        last = state["conversation_history"][-1]
        search_query = f"{last.get('query', '')} {query}"

    initial_chunks = hybrid_search(conn, embedder, search_query, project_id=project_id)

    # Step 2: Extract dependencies and do follow-up retrieval
    deps = extract_dependencies(initial_chunks)
    all_chunks = list(initial_chunks)

    # If we found references, retrieve additional context
    if deps and len(initial_chunks) < 10:
        # Pick top 2 dependency targets for follow-up
        follow_up_targets = [d["target"] for d in deps[:2]]
        for target in follow_up_targets:
            extra = hybrid_search(conn, embedder, target, top_k=3, project_id=project_id)
            # Add new chunks that aren't duplicates
            existing_keys = {(c.file_path, c.start_char, c.end_char) for c in all_chunks}
            for chunk in extra:
                key = (chunk.file_path, chunk.start_char, chunk.end_char)
                if key not in existing_keys:
                    all_chunks.append(chunk)
                    existing_keys.add(key)

    # Step 3: Build prompt and explain
    code_context = _format_context(all_chunks)

    prompt_parts = []

    # Add memory context if available
    if state["episodic_memories"] or state["semantic_memories"]:
        memory_ctx = _format_memory_context(
            state["episodic_memories"], state["semantic_memories"],
        )
        prompt_parts.append(f"Memory context:\n{memory_ctx}")

    # Add conversation history for follow-ups
    if state["query_type"] == "follow_up" and state["conversation_history"]:
        history_ctx = _format_history_context(state["conversation_history"])
        prompt_parts.append(history_ctx)

    prompt_parts.append(f"Retrieved code context:\n\n{code_context}")
    prompt_parts.append(f"Question: {query}")

    messages = [
        SystemMessage(content=NAVIGATION_SYSTEM_PROMPT),
        HumanMessage(content="\n\n".join(prompt_parts)),
    ]

    response = llm.invoke(messages)
    explored_files = list(dict.fromkeys(c.file_path for c in all_chunks))

    return {
        "response": ExplanationResult(
            explanation=response.content,
            sources=all_chunks,
        ),
        "dependencies": deps,
        "explored_files": explored_files,
    }


def plan_exploration(state: NavigationState) -> dict:
    """Plan and execute a multi-step exploration for broad questions.

    1. Ask LLM to plan search steps
    2. Execute each search step
    3. Synthesise a coherent walkthrough
    """
    llm = state["llm"]
    conn = state["conn"]
    embedder = state["embedder"]
    query = state["query"]
    project_id = state["project_id"]

    # Step 1: Plan search steps
    plan_messages = [
        HumanMessage(content=EXPLORATION_PLAN_PROMPT.format(query=query)),
    ]
    plan_response = llm.invoke(plan_messages)
    plan_text = plan_response.content

    # Parse numbered steps into search queries
    steps = re.findall(r"\d+\.\s*(.+)", plan_text)
    if not steps:
        steps = [query]  # Fallback to original query

    # Step 2: Execute each search step and collect chunks
    all_chunks = []
    existing_keys: set[tuple[str, int, int]] = set()
    for step_query in steps[:4]:  # Max 4 steps
        chunks = hybrid_search(conn, embedder, step_query.strip(), top_k=5, project_id=project_id)
        for chunk in chunks:
            key = (chunk.file_path, chunk.start_char, chunk.end_char)
            if key not in existing_keys:
                all_chunks.append(chunk)
                existing_keys.add(key)

    # Step 3: Synthesise walkthrough
    code_context = _format_context(all_chunks)

    synth_messages = [
        SystemMessage(content=EXPLORATION_SYNTHESISE_PROMPT),
        HumanMessage(
            content=(
                f"Original question: {query}\n\n"
                f"Exploration plan:\n{plan_text}\n\n"
                f"Retrieved code:\n\n{code_context}"
            ),
        ),
    ]
    synth_response = llm.invoke(synth_messages)

    deps = extract_dependencies(all_chunks)
    explored_files = list(dict.fromkeys(c.file_path for c in all_chunks))

    return {
        "response": ExplanationResult(
            explanation=synth_response.content,
            sources=all_chunks,
        ),
        "dependencies": deps,
        "explored_files": explored_files,
    }


def update_memory(state: NavigationState) -> dict:
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


def build_navigation_graph() -> Any:
    """Build and compile the intelligent navigation state graph.

    Graph structure:
        check_memory → classify_query → route_by_type →
            handle_map → update_memory → END
            plan_exploration → update_memory → END
            multi_step_retrieve → update_memory → END
    """
    graph = StateGraph(NavigationState)

    graph.add_node("check_memory", check_memory)
    graph.add_node("classify_query", classify_query)
    graph.add_node("handle_map", handle_map_query)
    graph.add_node("plan_exploration", plan_exploration)
    graph.add_node("multi_step_retrieve", multi_step_retrieve)
    graph.add_node("update_memory", update_memory)

    graph.set_entry_point("check_memory")
    graph.add_edge("check_memory", "classify_query")
    graph.add_conditional_edges(
        "classify_query",
        route_by_type,
        {
            "handle_map": "handle_map",
            "plan_exploration": "plan_exploration",
            "multi_step_retrieve": "multi_step_retrieve",
        },
    )
    graph.add_edge("handle_map", "update_memory")
    graph.add_edge("plan_exploration", "update_memory")
    graph.add_edge("multi_step_retrieve", "update_memory")
    graph.add_edge("update_memory", END)

    return graph.compile()
