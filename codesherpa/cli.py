"""CLI entry point for CodeSherpa."""

import argparse
import sys

from codesherpa.config import MissingConfigError, load_config
from codesherpa.db import DatabaseConnectionError, get_connection
from codesherpa.embeddings import CodeRankEmbedder
from codesherpa.ingestion import ensure_schema, ingest
from codesherpa.repo import RepoError, resolve_source


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="codesherpa",
        description="AI-powered codebase exploration and explanation tool",
    )
    parser.add_argument(
        "source",
        help="Path to a local repository or a GitHub URL",
    )
    parser.add_argument(
        "--project",
        default=None,
        help="Name for the project (used for isolation and metadata)",
    )
    return parser


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
        local_path = resolve_source(args.source)
    except RepoError as exc:
        print(f"Source error: {exc}", file=sys.stderr)
        sys.exit(1)

    project_name = args.project or local_path.rstrip("/").split("/")[-1]
    print(f"CodeSherpa: Indexing '{project_name}' from {args.source}")

    try:
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
    finally:
        conn.close()
