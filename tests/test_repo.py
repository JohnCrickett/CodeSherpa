"""Tests for repository source resolution (local paths and GitHub URLs)."""

import pytest

from codesherpa.repo import RepoError, _authenticated_url, resolve_source


class TestResolveLocalPath:
    """Tests for local directory sources."""

    def test_returns_path_for_existing_directory(self, tmp_path):
        result = resolve_source(str(tmp_path))
        assert result == str(tmp_path)

    def test_raises_for_nonexistent_path(self):
        with pytest.raises(RepoError, match="does not exist"):
            resolve_source("/no/such/path")

    def test_raises_for_file_not_directory(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello")
        with pytest.raises(RepoError, match="not a directory"):
            resolve_source(str(f))


class TestResolveGitHubURL:
    """Tests for GitHub URL cloning."""

    def test_clones_github_https_url(self, mocker, tmp_path):
        mock_run = mocker.patch("codesherpa.repo.subprocess.run")
        cache_dir = tmp_path / "cache"
        mocker.patch("codesherpa.repo.CACHE_DIR", cache_dir)
        mocker.patch.dict("os.environ", {}, clear=True)

        # The clone target won't exist yet, so it should clone
        result = resolve_source("https://github.com/owner/repo")

        expected_path = str(cache_dir / "owner_repo")
        assert result == expected_path
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert "clone" in args[0][0]
        assert "https://github.com/owner/repo" in args[0][0]

    def test_pulls_if_already_cloned(self, mocker, tmp_path):
        mock_run = mocker.patch("codesherpa.repo.subprocess.run")
        cache_dir = tmp_path / "cache"
        mocker.patch("codesherpa.repo.CACHE_DIR", cache_dir)
        mocker.patch.dict("os.environ", {}, clear=True)

        # Pre-create the clone directory with a .git folder
        clone_dir = cache_dir / "owner_repo"
        (clone_dir / ".git").mkdir(parents=True)

        result = resolve_source("https://github.com/owner/repo")

        assert result == str(clone_dir)
        args = mock_run.call_args
        assert "pull" in args[0][0]

    def test_parses_trailing_slash_and_dotgit(self, mocker, tmp_path):
        mock_run = mocker.patch("codesherpa.repo.subprocess.run")
        cache_dir = tmp_path / "cache"
        mocker.patch("codesherpa.repo.CACHE_DIR", cache_dir)
        mocker.patch.dict("os.environ", {}, clear=True)

        resolve_source("https://github.com/owner/repo.git/")

        expected_path = cache_dir / "owner_repo"
        args = mock_run.call_args
        assert str(expected_path) in args[0][0]

    def test_raises_on_clone_failure(self, mocker, tmp_path):
        import subprocess

        mock_run = mocker.patch("codesherpa.repo.subprocess.run")
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")
        cache_dir = tmp_path / "cache"
        mocker.patch("codesherpa.repo.CACHE_DIR", cache_dir)
        mocker.patch.dict("os.environ", {}, clear=True)

        with pytest.raises(RepoError, match="Failed to clone"):
            resolve_source("https://github.com/owner/repo")

    def test_clones_github_ssh_url(self, mocker, tmp_path):
        mock_run = mocker.patch("codesherpa.repo.subprocess.run")
        cache_dir = tmp_path / "cache"
        mocker.patch("codesherpa.repo.CACHE_DIR", cache_dir)

        result = resolve_source("git@github.com:owner/repo.git")

        expected_path = str(cache_dir / "owner_repo")
        assert result == expected_path
        mock_run.assert_called_once()
        args = mock_run.call_args
        assert "clone" in args[0][0]
        assert "git@github.com:owner/repo.git" in args[0][0]

    def test_ssh_url_without_dotgit(self, mocker, tmp_path):
        mocker.patch("codesherpa.repo.subprocess.run")
        cache_dir = tmp_path / "cache"
        mocker.patch("codesherpa.repo.CACHE_DIR", cache_dir)

        result = resolve_source("git@github.com:owner/repo")

        assert result == str(cache_dir / "owner_repo")

    def test_non_github_url_raises(self):
        with pytest.raises(RepoError, match="not a valid"):
            resolve_source("https://gitlab.com/owner/repo")

    def test_clone_uses_github_token(self, mocker, tmp_path):
        mock_run = mocker.patch("codesherpa.repo.subprocess.run")
        cache_dir = tmp_path / "cache"
        mocker.patch("codesherpa.repo.CACHE_DIR", cache_dir)
        mocker.patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_test123"})

        resolve_source("https://github.com/owner/private-repo")

        args = mock_run.call_args[0][0]
        assert "clone" in args
        assert "https://ghp_test123@github.com/owner/private-repo" in args

    def test_pull_updates_remote_with_token(self, mocker, tmp_path):
        mock_run = mocker.patch("codesherpa.repo.subprocess.run")
        cache_dir = tmp_path / "cache"
        mocker.patch("codesherpa.repo.CACHE_DIR", cache_dir)
        mocker.patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_test123"})

        clone_dir = cache_dir / "owner_repo"
        (clone_dir / ".git").mkdir(parents=True)

        resolve_source("https://github.com/owner/repo")

        # First call sets the remote URL, second call pulls
        calls = mock_run.call_args_list
        assert len(calls) == 2
        assert "set-url" in calls[0][0][0]
        assert "https://ghp_test123@github.com/owner/repo" in calls[0][0][0]
        assert "pull" in calls[1][0][0]


class TestAuthenticatedUrl:
    """Tests for GITHUB_TOKEN injection into URLs."""

    def test_injects_token_into_https_url(self, mocker):
        mocker.patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_abc"})
        result = _authenticated_url("https://github.com/owner/repo")
        assert result == "https://ghp_abc@github.com/owner/repo"

    def test_returns_original_without_token(self, mocker):
        mocker.patch.dict("os.environ", {}, clear=True)
        result = _authenticated_url("https://github.com/owner/repo")
        assert result == "https://github.com/owner/repo"

    def test_ignores_ssh_urls(self, mocker):
        mocker.patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_abc"})
        result = _authenticated_url("git@github.com:owner/repo.git")
        assert result == "git@github.com:owner/repo.git"

    def test_ignores_non_github_urls(self, mocker):
        mocker.patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_abc"})
        result = _authenticated_url("https://gitlab.com/owner/repo")
        assert result == "https://gitlab.com/owner/repo"
