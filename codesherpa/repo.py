"""Repository source resolution: local paths and GitHub URL cloning."""

import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

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


def _clone_or_pull(url: str) -> str:
    """Clone a GitHub repo, or pull if already cloned."""
    owner, repo = _parse_github_source(url)
    dest = CACHE_DIR / f"{owner}_{repo}"

    try:
        if (dest / ".git").is_dir():
            subprocess.run(
                f"git -C {dest} pull --ff-only",
                shell=True,
                check=True,
                capture_output=True,
            )
        else:
            dest.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                f"git clone {url} {dest}",
                shell=True,
                check=True,
                capture_output=True,
            )
    except subprocess.CalledProcessError as exc:
        raise RepoError(
            f"Failed to clone '{url}'. Ensure the URL is correct and git is installed. "
            f"Details: {exc.stderr}"
        ) from exc

    return str(dest)
