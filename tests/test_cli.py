"""Tests for the CLI entry point."""

import pytest

from codesherpa.cli import build_parser


class TestCLI:
    """Tests for the CLI argument parser."""

    def test_requires_source_argument(self):
        """CLI requires a source path or URL argument."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_accepts_source_path(self):
        """CLI accepts a source path positional argument."""
        parser = build_parser()
        args = parser.parse_args(["/path/to/repo"])
        assert args.source == "/path/to/repo"

    def test_accepts_project_flag(self):
        """CLI accepts --project to name the project."""
        parser = build_parser()
        args = parser.parse_args(["--project", "myproject", "/path/to/repo"])
        assert args.project == "myproject"
        assert args.source == "/path/to/repo"

    def test_project_defaults_to_none(self):
        """--project defaults to None when not provided."""
        parser = build_parser()
        args = parser.parse_args(["/path/to/repo"])
        assert args.project is None

    def test_accepts_github_url(self):
        """CLI accepts a GitHub URL as the source."""
        parser = build_parser()
        args = parser.parse_args(["https://github.com/user/repo"])
        assert args.source == "https://github.com/user/repo"

    def test_displays_help(self, capsys):
        """CLI displays usage information with --help."""
        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0
