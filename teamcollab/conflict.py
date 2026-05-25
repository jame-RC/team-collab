"""Pull-modify-push retry for shared files (glossary etc.).

The motivating problem: two members may concurrently update the same shared
file (typically ``glossary.json``). With pure last-write-wins, one update is
lost. We solve it by wrapping the write in a retry loop:

    pull --rebase  →  apply user-supplied modify_fn  →  commit  →  push
    on ConflictError or rebase failure: re-pull, re-apply, repeat (up to N)

The ``modify_fn`` is a thunk that re-reads the file from disk and applies the
caller's *intent* (e.g. "set glossary['mlops'] = 'Machine Learning Operations'")
— NOT a precomputed diff. That way each retry sees the latest pulled state and
the merge is semantic rather than textual.

For OfflineError on push, the local commit is preserved and the failure is
already journalled in ``.teamcollab/pending_pushes.log`` by GitRepo.push;
:func:`with_pull_modify_push_retry` swallows it so the caller still sees a
successful local write (eventual consistency on next sync).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from teamcollab.git_ops import (
    ConflictError,
    GitRepo,
    OfflineError,
)

logger = logging.getLogger(__name__)


@dataclass
class RetryResult:
    """What happened after the retry loop settled."""

    sha: str | None  # local commit SHA, or None if modify_fn produced no diff
    attempts: int  # how many pull-modify-push cycles we ran
    pushed: bool  # did the push succeed (False means we're offline / queued)


class RetryExhaustedError(RuntimeError):
    """Raised when ``max_retries`` rebases all failed to land cleanly."""


def with_pull_modify_push_retry(
    repo: GitRepo,
    modify_fn: Callable[[Path], Iterable[str | Path] | None],
    *,
    commit_message: str,
    branch: str | None = "main",
    max_retries: int = 3,
) -> RetryResult:
    """Run ``modify_fn`` against ``repo`` with pull-then-push semantics.

    ``modify_fn`` receives the repo's working-tree path and is expected to:

    * read whatever shared file(s) it cares about,
    * mutate them on disk,
    * return an iterable of paths that should be ``git add``-ed (or None
      if the function staged things itself / produced no changes).

    Behavior:

    * On every attempt we ``pull --rebase`` first so the modify sees the
      latest published state.
    * If the modify yields no staged change (``commit`` returns None), we
      return early with ``sha=None``; this is not an error — it means the
      caller's intent was already satisfied by what we just pulled.
    * On :class:`ConflictError` (push rejected), the loop retries: pull,
      re-run modify_fn against the freshly pulled state, commit, push.
    * On :class:`OfflineError` we keep the local commit and return
      ``pushed=False``. The pending-push log is already updated by
      ``GitRepo.push``.
    """
    last_err: ConflictError | None = None

    for attempt in range(1, max_retries + 1):
        # 1. Sync down. Offline pull is non-fatal; we work from local state.
        try:
            repo.pull(branch=branch)
        except OfflineError:
            logger.info("pull offline on attempt %d; continuing with local state", attempt)
        except ConflictError as e:
            # Rebase blew up mid-pull (e.g. uncommitted local edits collide).
            # We don't try to auto-resolve here — surface it.
            raise e

        # 2. Apply caller intent against the freshly pulled tree.
        to_add = modify_fn(repo.path)
        if to_add:
            repo.add(to_add)

        sha = repo.commit(commit_message)
        if sha is None:
            # Nothing changed — caller's desired state already on disk.
            return RetryResult(sha=None, attempts=attempt, pushed=True)

        # 3. Try to publish.
        try:
            repo.push(branch=branch)
            return RetryResult(sha=sha, attempts=attempt, pushed=True)
        except OfflineError:
            return RetryResult(sha=sha, attempts=attempt, pushed=False)
        except ConflictError as e:
            last_err = e
            logger.info(
                "push rejected on attempt %d (%s); will pull --rebase and retry",
                attempt,
                e,
            )
            # Loop around: next iteration will pull --rebase, which is exactly
            # how we incorporate the remote's newer commits before re-trying.
            continue

    raise RetryExhaustedError(
        f"could not land changes after {max_retries} attempts; last error: {last_err}"
    )
