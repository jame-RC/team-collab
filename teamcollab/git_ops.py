"""GitPython-backed wrapper for the local clone.

Design goals:

* All MCP tools talk to git through this module — never via subprocess directly.
* Offline degradation: pull/push failures are caught and surfaced as typed
  errors so the caller can decide whether to keep working against the local
  clone or to abort.
* Push failures are logged to ``.teamcollab/pending_pushes.log`` so they can
  be retried later (the conflict retry layer in :mod:`teamcollab.conflict`
  builds on top of this).
* Commit messages are produced by :class:`EventEnvelope` from
  :mod:`teamcollab.contracts`; this module only takes already-formatted
  strings.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from git import GitCommandError, InvalidGitRepositoryError, Repo
from git.exc import NoSuchPathError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------


class GitOpsError(Exception):
    """Base class for everything raised from this module."""


class OfflineError(GitOpsError):
    """Network unreachable / remote unresponsive. Local state is still usable."""


class AuthError(GitOpsError):
    """Remote refused credentials. User must re-auth (e.g. ``gh auth login``)."""


class ConflictError(GitOpsError):
    """Non-fast-forward push or unresolvable rebase. Caller should retry via conflict layer."""


class RepoNotFoundError(GitOpsError):
    """Path does not contain a git repository."""


# ---------------------------------------------------------------------------
# Heuristics for classifying GitCommandError
# ---------------------------------------------------------------------------


_OFFLINE_MARKERS = (
    "could not resolve host",
    "failed to connect",
    "operation timed out",
    "network is unreachable",
    "temporary failure in name resolution",
    "ssl_error",
    "could not read from remote",
)
_AUTH_MARKERS = (
    "authentication failed",
    "permission denied (publickey)",
    "permission denied",
    "403",
    "could not read username",
    "invalid credentials",
)
_CONFLICT_MARKERS = (
    "non-fast-forward",
    "rejected",
    "fetch first",
    "would be overwritten",
    "merge conflict",
    "conflict (",
)


def _classify(err: GitCommandError) -> GitOpsError:
    blob = f"{err.stderr or ''} {err.stdout or ''}".lower()
    if any(m in blob for m in _OFFLINE_MARKERS):
        return OfflineError(str(err))
    if any(m in blob for m in _AUTH_MARKERS):
        return AuthError(str(err))
    if any(m in blob for m in _CONFLICT_MARKERS):
        return ConflictError(str(err))
    return GitOpsError(str(err))


# ---------------------------------------------------------------------------
# GitRepo wrapper
# ---------------------------------------------------------------------------


@dataclass
class CommitInfo:
    sha: str
    message: str
    author: str
    ts: float  # unix timestamp


class GitRepo:
    """Thin wrapper around :class:`git.Repo` with offline-aware semantics."""

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        try:
            self._repo = Repo(self.path)
        except (InvalidGitRepositoryError, NoSuchPathError) as e:
            raise RepoNotFoundError(f"no git repo at {self.path}") from e

    # -- construction helpers ------------------------------------------------

    @classmethod
    def clone(cls, url: str, dest: str | Path) -> GitRepo:
        dest = Path(dest).resolve()
        try:
            Repo.clone_from(url, dest)
        except GitCommandError as e:
            raise _classify(e) from e
        return cls(dest)

    @classmethod
    def init(cls, path: str | Path, initial_branch: str = "main") -> GitRepo:
        path = Path(path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        try:
            Repo.init(path, initial_branch=initial_branch)
        except GitCommandError as e:
            raise _classify(e) from e
        return cls(path)

    # -- read ----------------------------------------------------------------

    def log(self, max_count: int = 100, since_sha: str | None = None) -> list[CommitInfo]:
        """Return commits newest-first. ``since_sha`` is exclusive (skip past it)."""
        rev = "HEAD"
        kwargs: dict = {"max_count": max_count}
        try:
            commits = list(self._repo.iter_commits(rev, **kwargs))
        except (GitCommandError, ValueError):
            return []
        if since_sha is not None:
            try:
                cut = next(i for i, c in enumerate(commits) if c.hexsha == since_sha)
                commits = commits[:cut]
            except StopIteration:
                pass
        return [
            CommitInfo(
                sha=c.hexsha,
                message=c.message if isinstance(c.message, str) else c.message.decode("utf-8", "replace"),
                author=str(c.author),
                ts=float(c.committed_date),
            )
            for c in commits
        ]

    def head_sha(self) -> str | None:
        try:
            return self._repo.head.commit.hexsha
        except Exception:
            return None

    def is_dirty(self) -> bool:
        return self._repo.is_dirty(untracked_files=True)

    # -- write ---------------------------------------------------------------

    def add(self, paths: Iterable[str | Path]) -> None:
        rel: list[str] = []
        for p in paths:
            pp = Path(p)
            if pp.is_absolute():
                pp = pp.relative_to(self.path)
            rel.append(str(pp).replace("\\", "/"))
        if rel:
            self._repo.index.add(rel)

    def commit(self, message: str, allow_empty: bool = False) -> str | None:
        """Commit the current index. Returns SHA, or None when nothing to commit."""
        if not allow_empty and not self._repo.index.diff("HEAD" if self._repo.head.is_valid() else None):
            # Nothing staged; also nothing untracked-but-staged. Skip.
            if not self._repo.is_dirty(index=True, working_tree=False, untracked_files=False):
                return None
        try:
            commit = self._repo.index.commit(message)
        except GitCommandError as e:
            raise _classify(e) from e
        return commit.hexsha

    # -- sync ----------------------------------------------------------------

    def pull(self, remote: str = "origin", branch: str | None = None, rebase: bool = True) -> None:
        if remote not in [r.name for r in self._repo.remotes]:
            return  # local-only repo (e.g. tests); pull is a no-op
        try:
            kwargs: dict = {}
            if rebase:
                kwargs["rebase"] = True
            args = [remote]
            if branch:
                args.append(branch)
            self._repo.git.pull(*args, **kwargs)
        except GitCommandError as e:
            raise _classify(e) from e

    def push(self, remote: str = "origin", branch: str | None = None) -> None:
        if remote not in [r.name for r in self._repo.remotes]:
            self._log_pending(f"push skipped: no remote ({remote})")
            return
        try:
            args = [remote]
            if branch:
                args.append(branch)
            self._repo.git.push(*args)
        except GitCommandError as e:
            err = _classify(e)
            if isinstance(err, OfflineError):
                self._log_pending(f"offline: {e.stderr or e}")
            raise err from e

    # -- internal helpers ----------------------------------------------------

    def _log_pending(self, line: str) -> None:
        log_dir = self.path / ".teamcollab"
        log_dir.mkdir(exist_ok=True)
        with (log_dir / "pending_pushes.log").open("a", encoding="utf-8") as f:
            f.write(line.rstrip() + "\n")
