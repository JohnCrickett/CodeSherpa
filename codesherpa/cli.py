"""CLI entry point for CodeSherpa."""

import argparse
import sys

from codesherpa.config import MissingConfigError, load_config
from codesherpa.db import DatabaseConnectionError, get_connection


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
        conn.close()
    except DatabaseConnectionError as exc:
        print(f"Database error: {exc}", file=sys.stderr)
        sys.exit(1)

    project_name = args.project or args.source.rstrip("/").split("/")[-1]
    print(f"CodeSherpa: Indexing '{project_name}' from {args.source}")
