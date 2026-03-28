"""CLI entry point for CodeSherpa."""

import argparse
import sys

from codesherpa.config import MissingConfigError, load_config
from codesherpa.db import DatabaseConnectionError, get_connection
from codesherpa.embeddings import CodeRankEmbedder
from codesherpa.explanation import ExplanationResult, explain
from codesherpa.ingestion import ensure_schema, ingest
from codesherpa.llm import get_llm
from codesherpa.repo import RepoError, resolve_source
from codesherpa.retrieval import SearchResult, hybrid_search


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="codesherpa",
        description="AI-powered codebase exploration and explanation tool",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ingest subcommand
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a codebase")
    ingest_parser.add_argument(
        "source",
        help="Path to a local repository or a GitHub URL",
    )
    ingest_parser.add_argument(
        "--project",
        default=None,
        help="Name for the project (used for isolation and metadata)",
    )

    # query subcommand
    subparsers.add_parser("query", help="Search ingested code interactively")

    # ask subcommand
    ask_parser = subparsers.add_parser("ask", help="Ask a question about ingested code")
    ask_parser.add_argument("question", help="Natural language question about the codebase")

    return parser


def format_results(results: list[SearchResult]) -> str:
    """Format search results for display.

    Args:
        results: List of SearchResult to format.

    Returns:
        Formatted string ready for printing.
    """
    if not results:
        return "No relevant code found."

    parts = []
    for i, r in enumerate(results, 1):
        parts.append(
            f"--- Result {i} ---\n"
            f"File: {r.file_path} (chars {r.start_char}-{r.end_char})\n"
            f"Type: {r.chunk_type} | Language: {r.language} | Score: {r.score:.2f}\n"
            f"\n{r.code_text}\n"
        )
    return "\n".join(parts)


def format_explanation(result: ExplanationResult) -> str:
    """Format an explanation result for display.

    Args:
        result: The ExplanationResult to format.

    Returns:
        Formatted string ready for printing.
    """
    parts = [result.explanation, ""]
    if result.sources:
        parts.append("--- Sources ---")
        for i, s in enumerate(result.sources, 1):
            parts.append(
                f"  [{i}] {s.file_path} ({s.chunk_type}, chars {s.start_char}-{s.end_char})"
            )
    return "\n".join(parts)


def run_query_repl(conn, embedder: CodeRankEmbedder) -> None:
    """Run the interactive query REPL.

    Args:
        conn: Oracle Database connection.
        embedder: Embedding client for query encoding.
    """
    print("CodeSherpa query mode. Type 'quit' or 'exit' to leave.\n")
    while True:
        try:
            query = input("query> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if query.strip().lower() in ("quit", "exit"):
            break

        if not query.strip():
            continue

        results = hybrid_search(conn, embedder, query.strip())
        print(format_results(results))


def main(argv: list[str] | None = None) -> None:
    """Main entry point for the CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config()
    except MissingConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        conn = get_connection(
            dsn=config.oracle_dsn,
            user=config.oracle_user,
            password=config.oracle_password,
        )
    except DatabaseConnectionError as exc:
        print(f"Database error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.command == "ingest":
            try:
                local_path = resolve_source(args.source)
            except RepoError as exc:
                print(f"Source error: {exc}", file=sys.stderr)
                sys.exit(1)

            project_name = args.project or local_path.rstrip("/").split("/")[-1]
            print(f"CodeSherpa: Indexing '{project_name}' from {args.source}")

            ensure_schema(conn)
            print("Loading embedding model...")
            embedder = CodeRankEmbedder()
            print("Ingesting codebase...")
            stats = ingest(conn, embedder, local_path)
            print(
                f"Done: {stats['chunks_stored']} chunks stored, "
                f"{stats['files_skipped']} files unchanged, "
                f"{stats['files_updated']} files updated, "
                f"{stats['files_deleted']} files removed."
            )

        elif args.command == "query":
            print("Loading embedding model...")
            embedder = CodeRankEmbedder()
            run_query_repl(conn, embedder)

        elif args.command == "ask":
            print("Loading embedding model...")
            embedder = CodeRankEmbedder()
            llm = get_llm(api_key=config.llm_api_key, model=config.llm_model)
            result = explain(conn, embedder, llm, args.question)
            print(format_explanation(result))
    finally:
        conn.close()
