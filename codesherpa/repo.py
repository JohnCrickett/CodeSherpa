"""Repository source resolution: local paths and GitHub URL cloning."""

import logging
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".cache" / "codesherpa"

_SSH_RE = re.compile(r"^git@github\.com:([^/]+)/(.+?)(?:\.git)?/?$")


class RepoError(Exception):
    """Raised when the source cannot be resolved to a local directory."""


def _parse_github_source(source: str) -> tuple[str, str]:
    """Extract owner and repo name from a GitHub URL (HTTPS or SSH).

    Returns:
        A tuple of (owner, repo).

    Raises:
        RepoError: If the source is not a valid GitHub repository URL.
    """
    ssh_match = _SSH_RE.match(source)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    parsed = urlparse(source)
    if parsed.hostname not in ("github.com", "www.github.com"):
        raise RepoError(f"'{source}' is not a valid GitHub URL.")

    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.split("/")
    if len(parts) < 2:
        raise RepoError(f"'{source}' is not a valid GitHub repository URL.")
    return parts[0], parts[1]


def _is_git_url(source: str) -> bool:
    """Check if source looks like a git URL (HTTPS or SSH)."""
    return (
        source.startswith("https://")
        or source.startswith("http://")
        or source.startswith("git@")
    )


def resolve_source(source: str) -> str:
    """Resolve a source argument to a local directory path.

    If source is a local path, validates it exists and is a directory.
    If source is a GitHub URL (HTTPS or SSH), clones (or pulls) the repo
    into a cache directory.

    Args:
        source: A local path or GitHub URL.

    Returns:
        The absolute path to the local directory.

    Raises:
        RepoError: If the source cannot be resolved.
    """
    if _is_git_url(source):
        return _clone_or_pull(source)

    path = Path(source)
    if not path.exists():
        raise RepoError(f"Path '{source}' does not exist.")
    if not path.is_dir():
        raise RepoError(f"Path '{source}' is not a directory.")
    return str(path)


def _sanitize_git_output(text: str | bytes) -> str:
    """Remove tokens from git command output to avoid leaking credentials."""
    s = text.decode("utf-8", errors="replace") if isinstance(text, bytes) else text
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        s = s.replace(token, "***")
    return s


def _authenticated_url(url: str) -> str:
    """If GITHUB_TOKEN is set, inject it into an HTTPS GitHub URL for auth."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return url
    parsed = urlparse(url)
    if parsed.scheme in ("https", "http") and parsed.hostname in (
        "github.com",
        "www.github.com",
    ):
        return parsed._replace(netloc=f"{token}@{parsed.hostname}").geturl()
    return url


def _clone_or_pull(url: str) -> str:
    """Clone a GitHub repo, or pull if already cloned."""
    owner, repo = _parse_github_source(url)
    dest = CACHE_DIR / f"{owner}_{repo}"
    auth_url = _authenticated_url(url)

    if (dest / ".git").is_dir():
        # Already cloned — update remote URL (token may have changed) and pull
        try:
            subprocess.run(
                ["git", "-C", str(dest), "remote", "set-url", "origin", auth_url],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(dest), "pull", "--ff-only"],
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            logger.warning("git pull failed for '%s', using cached copy: %s", url, exc)
    else:
        # Fresh clone required
        try:
            dest.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", auth_url, str(dest)],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as exc:
            detail = _sanitize_git_output(exc.stderr or b"")
            token = os.environ.get("GITHUB_TOKEN")
            hint = ""
            if "403" in detail or "Authentication" in detail:
                if token:
                    hint = (
                        " Your GITHUB_TOKEN may lack access to this repo."
                        " Ensure it has 'Contents: Read' permission."
                    )
                else:
                    hint = (
                        " This may be a private repo."
                        " Set GITHUB_TOKEN with 'Contents: Read' permission."
                    )
            elif not token and ("Username" in detail or "could not read" in detail):
                hint = (
                    " This may be a private repo."
                    " Set GITHUB_TOKEN with 'Contents: Read' permission."
                )
            raise RepoError(
                f"Failed to clone '{url}'.{hint} Details: {detail}"
            ) from exc

    return str(dest)
