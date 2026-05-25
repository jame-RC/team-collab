"""Minimum coverage tests for the misc tools.

Covers ``glossary_get`` / ``glossary_update`` / ``events_recent`` /
``sync_now`` / ``search_blackboard`` plus a smoke for ``team_init`` /
``team_join``. One success + one degraded/failure path per tool, per M1.6.

All tests are hermetic: ``team_init`` is invoked with ``remote_url=None``
so no network is touched. ``sync_now`` is exercised against a repo with no
remote configured to verify offline tolerance.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from teamcollab.contracts import EventType, Glossary, Role
from teamcollab.tools._io import read_model
from teamcollab.tools._paths import glossary_json, members_json, project_json
from teamcollab.tools.events_recent import events_recent
from teamcollab.tools.glossary import glossary_get, glossary_update
from teamcollab.tools.search_blackboard import search_blackboard
from teamcollab.tools.sync_now import sync_now
from teamcollab.tools.team_init import team_init


@pytest.fixture
def repo_path(tmp_path: Path) -> Path:
    """A bootstrapped repo with no remote — sync is offline by construction."""
    root = tmp_path / "proj"
    team_init(
        local_path=root,
        title="demo",
        brief="a demo project",
        leader="alice",
    )
    from git import Repo
    g = Repo(root)
    g.git.config("user.email", "test@example.com")
    g.git.config("user.name", "test")
    return root


# ---------------------------------------------------------------------------
# team_init smoke
# ---------------------------------------------------------------------------


def test_team_init_writes_expected_layout(tmp_path: Path):
    root = tmp_path / "fresh"
    out = team_init(
        local_path=root,
        title="t",
        brief="b",
        leader="alice",
    )
    assert out["pushed"] is False  # no remote_url provided
    assert (root / ".git").exists()
    assert project_json(root).exists()
    assert members_json(root).exists()
    assert glossary_json(root).exists()
    assert (root / ".github" / "workflows" / "teamcollab.yml").exists()


# ---------------------------------------------------------------------------
# glossary_get / glossary_update
# ---------------------------------------------------------------------------


def test_glossary_get_empty_then_update(repo_path: Path):
    out = glossary_get(local_path=repo_path)
    assert out["count"] == 0
    assert out["entries"] == {}

    res = glossary_update(
        local_path=repo_path,
        term="latency",
        definition="time-to-first-byte",
        actor="alice",
        aliases=["ttfb"],
    )
    assert res["term"] == "latency"
    assert res["attempts"] >= 1

    g = read_model(glossary_json(repo_path), Glossary)
    assert "latency" in g.entries
    assert g.entries["latency"].definition == "time-to-first-byte"
    assert g.entries["latency"].aliases == ["ttfb"]


def test_glossary_get_specific_term_missing(repo_path: Path):
    out = glossary_get(local_path=repo_path, term="ghost-term")
    assert out["term"] == "ghost-term"
    assert out["entry"] is None


# ---------------------------------------------------------------------------
# events_recent
# ---------------------------------------------------------------------------


def test_events_recent_returns_project_created(repo_path: Path):
    out = events_recent(local_path=repo_path, limit=10)
    assert out["count"] >= 1
    types = [e["envelope"]["type"] for e in out["events"]]
    assert EventType.PROJECT_CREATED.value in types


def test_events_recent_type_filter_excludes(repo_path: Path):
    # Create a glossary update event so we have something to filter.
    glossary_update(
        local_path=repo_path,
        term="x",
        definition="y",
        actor="alice",
    )
    out = events_recent(
        local_path=repo_path,
        types=[EventType.GLOSSARY_UPDATED],
        limit=10,
    )
    assert out["count"] >= 1
    for e in out["events"]:
        assert e["envelope"]["type"] == EventType.GLOSSARY_UPDATED.value


# ---------------------------------------------------------------------------
# sync_now
# ---------------------------------------------------------------------------


def test_sync_now_offline_tolerated(repo_path: Path):
    out = sync_now(local_path=repo_path)
    # No remote configured → pull/push silently no-op in GitRepo (treated as
    # local-only); the call itself doesn't raise. head_sha is always present.
    assert out["pulled"] is True
    assert out["pushed"] is True
    assert out["head_sha"]
    assert out["pull_error"] is None
    assert out["push_error"] is None


def test_sync_now_offline_with_unreachable_remote(repo_path: Path, tmp_path: Path):
    # Configure an origin pointing at a nonexistent path → push/pull will
    # fail and be classified as OfflineError; sync_now must catch it.
    from git import Repo
    g = Repo(repo_path)
    bogus = tmp_path / "no-such-remote.git"
    g.create_remote("origin", str(bogus))

    out = sync_now(local_path=repo_path)
    assert out["pulled"] is False
    assert out["pushed"] is False
    assert out["pull_error"] is not None
    assert out["push_error"] is not None


# ---------------------------------------------------------------------------
# search_blackboard
# ---------------------------------------------------------------------------


def test_search_blackboard_finds_term(repo_path: Path):
    # project.json contains "demo" as the title.
    out = search_blackboard(local_path=repo_path, query="demo", top_k=5)
    assert out["query"] == "demo"
    assert out["count"] >= 1
    paths = {h["path"] for h in out["grep_hits"]}
    assert any(p.endswith("project.json") for p in paths)


def test_search_blackboard_zero_match(repo_path: Path):
    out = search_blackboard(
        local_path=repo_path,
        query="zzz-no-such-token-zzz",
        top_k=5,
    )
    assert out["count"] == 0
    assert out["grep_hits"] == []


# ---------------------------------------------------------------------------
# team_join (offline smoke — joining a non-existent remote is a clone failure;
# we only cover the "already cloned, re-join is idempotent" path here since
# that's the only network-free scenario)
# ---------------------------------------------------------------------------


def test_team_join_idempotent_existing_member(repo_path: Path):
    from teamcollab.tools.team_join import team_join

    # alice is already the leader from team_init — re-joining should be a no-op.
    out = team_join(
        remote_url="unused",
        local_path=repo_path,
        name="alice",
        role=Role.LEADER,
    )
    assert out["joined"] is False
    assert out["sha"] is None
