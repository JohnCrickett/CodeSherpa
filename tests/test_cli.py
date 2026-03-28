"""Tests for the CLI entry point."""

from unittest.mock import MagicMock, patch

import pytest

from codesherpa.cli import build_parser, format_results, run_query_repl
from codesherpa.retrieval import SearchResult


class TestCLI:
    """Tests for the CLI argument parser."""

    def test_requires_subcommand(self):
        """CLI requires a subcommand."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_ingest_accepts_source_path(self):
        """Ingest subcommand accepts a source path positional argument."""
        parser = build_parser()
        args = parser.parse_args(["ingest", "/path/to/repo"])
        assert args.command == "ingest"
        assert args.source == "/path/to/repo"

    def test_ingest_accepts_project_flag(self):
        """Ingest subcommand accepts --project to name the project."""
        parser = build_parser()
        args = parser.parse_args(["ingest", "--project", "myproject", "/path/to/repo"])
        assert args.project == "myproject"
        assert args.source == "/path/to/repo"

    def test_ingest_project_defaults_to_none(self):
        """--project defaults to None when not provided."""
        parser = build_parser()
        args = parser.parse_args(["ingest", "/path/to/repo"])
        assert args.project is None

    def test_ingest_accepts_github_url(self):
        """Ingest subcommand accepts a GitHub URL as the source."""
        parser = build_parser()
        args = parser.parse_args(["ingest", "https://github.com/user/repo"])
        assert args.source == "https://github.com/user/repo"

    def test_query_subcommand_exists(self):
        """Query subcommand is accepted by the parser."""
        parser = build_parser()
        args = parser.parse_args(["query"])
        assert args.command == "query"

    def test_displays_help(self, capsys):
        """CLI displays usage information with --help."""
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0


class TestFormatResults:
    """Tests for result formatting."""

    def test_formats_result_with_file_path_and_score(self):
        """Each result displays file path, chunk type, and relevance score."""
        results = [
            SearchResult("def foo(): pass", "src/main.py", "function", "python", 0, 15, 0.85),
        ]
        output = format_results(results)
        assert "src/main.py" in output
        assert "0.85" in output
        assert "def foo(): pass" in output

    def test_formats_multiple_results(self):
        """Multiple results are all included in the output."""
        results = [
            SearchResult("def a(): ...", "a.py", "function", "python", 0, 10, 0.9),
            SearchResult("class B: ...", "b.py", "class", "python", 0, 12, 0.6),
        ]
        output = format_results(results)
        assert "a.py" in output
        assert "b.py" in output

    def test_formats_no_results_message(self):
        """Empty results produce a 'no relevant code found' message."""
        output = format_results([])
        assert "no relevant code" in output.lower()

    def test_includes_character_position(self):
        """Output includes character position reference for each result."""
        results = [
            SearchResult("code", "x.py", "function", "python", 100, 200, 0.7),
        ]
        output = format_results(results)
        assert "100" in output
        assert "200" in output


class TestQueryREPL:
    """Tests for the query REPL loop."""

    def test_exits_on_quit(self):
        """REPL exits when user types 'quit'."""
        conn = MagicMock()
        embedder = MagicMock()

        with patch("builtins.input", side_effect=["quit"]), \
             patch("builtins.print"):
            run_query_repl(conn, embedder)

        # Should not have called hybrid_search for "quit"

    def test_exits_on_exit(self):
        """REPL exits when user types 'exit'."""
        conn = MagicMock()
        embedder = MagicMock()

        with patch("builtins.input", side_effect=["exit"]), \
             patch("builtins.print"):
            run_query_repl(conn, embedder)

    def test_exits_on_eof(self):
        """REPL exits on EOF (Ctrl+D)."""
        conn = MagicMock()
        embedder = MagicMock()

        with patch("builtins.input", side_effect=EOFError), \
             patch("builtins.print"):
            run_query_repl(conn, embedder)

    def test_processes_query_and_displays_results(self):
        """REPL calls hybrid_search and displays formatted results."""
        conn = MagicMock()
        embedder = MagicMock()
        mock_results = [
            SearchResult("def foo(): ...", "a.py", "function", "python", 0, 15, 0.9),
        ]

        with patch("builtins.input", side_effect=["find foo", "quit"]), \
             patch("codesherpa.cli.hybrid_search", return_value=mock_results), \
             patch("builtins.print") as mock_print:
            run_query_repl(conn, embedder)

        # Should have printed results containing the file path
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        assert "a.py" in printed

    def test_skips_empty_input(self):
        """REPL skips blank lines without searching."""
        conn = MagicMock()
        embedder = MagicMock()

        with patch("builtins.input", side_effect=["", "  ", "quit"]), \
             patch("codesherpa.cli.hybrid_search") as mock_search, \
             patch("builtins.print"):
            run_query_repl(conn, embedder)

        mock_search.assert_not_called()
