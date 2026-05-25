"""``team_init``: bootstrap a fresh team-collab repo at a local path.

What it does (idempotent on a fresh path):

1. ``git init`` (default branch ``main``).
2. Write ``project.json`` (title, brief, deadline, leader as first member).
3. Write ``.teamcollab/members.json`` with the leader.
4. Write ``glossary.json`` (empty).
5. Write ``.github/workflows/teamcollab.yml`` (the lazy-server workflow).
6. Write ``.gitignore`` (excludes pending-push log, cache).
7. Make ``tasks/``, ``artifacts/``, ``reviews/``, ``final/`` placeholder dirs.
8. Commit everything with an :class:`EventEnvelope` of type ``project_created``.
9. If ``remote_url`` is provided, configure ``origin`` and push.

The ``gh repo create`` step lives in the slash command (shell side) — this
function only deals with local + git push. Keeping it out of the tool keeps
unit tests hermetic.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from teamcollab.contracts import (
    EventEnvelope,
    EventType,
    Glossary,
    MemberInfo,
    ProjectMeta,
    Role,
)
from teamcollab.git_ops import GitRepo
from teamcollab.tools import _paths
from teamcollab.tools._io import write_json, write_model

WORKFLOW_YAML = """\
name: teamcollab
on:
  push:
    paths:
      - 'artifacts/**'
      - 'reviews/**'
      - 'tasks/**'
    branches: [main]

jobs:
  dispatch:
    if: ${{ vars.TEAMCOLLAB_ENABLED != 'false' }}
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: write
    env:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      LLM_API_KEY: ${{ secrets.LLM_API_KEY || secrets.ANTHROPIC_API_KEY }}
      LLM_BASE_URL: ${{ vars.LLM_BASE_URL }}
      LLM_MODEL: ${{ vars.LLM_MODEL }}

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 10

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install anthropic pyyaml pydantic

      - name: Parse latest commit envelope
        id: parse
        run: |
          MSG=$(git log -1 --format='%B')
          if echo "$MSG" | grep -q '^\\[teamcollab\\]'; then
            TYPE=$(echo "$MSG" | head -1 | sed 's/\\[teamcollab\\] //')
            echo "type=$TYPE" >> "$GITHUB_OUTPUT"
            echo "has_envelope=true" >> "$GITHUB_OUTPUT"
          else
            echo "has_envelope=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Run reviewer
        if: steps.parse.outputs.has_envelope == 'true' && steps.parse.outputs.type == 'artifact_submitted'
        run: python scripts/run_reviewer.py
        env:
          COMMIT_MSG: ${{ github.event.head_commit.message }}

      - name: Run integrator
        if: steps.parse.outputs.has_envelope == 'true' && steps.parse.outputs.type == 'review_posted'
        run: python scripts/run_integrator.py
        env:
          COMMIT_MSG: ${{ github.event.head_commit.message }}
"""

GITIGNORE = """\
__pycache__/
*.pyc
.venv/
.teamcollab/cache/
.teamcollab/pending_pushes.log
"""


def _copy_runner_scripts(root: Path) -> list[Path]:
    """Copy run_reviewer.py and run_integrator.py from templates into the new repo."""
    scripts_dir = root / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    templates_base = Path(__file__).resolve().parent.parent.parent / "templates" / "scripts"
    written: list[Path] = []
    for name in ("run_reviewer.py", "run_integrator.py"):
        src = templates_base / name
        dst = scripts_dir / name
        if src.exists():
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            dst.write_text(f"# placeholder: {name} (templates not found at build time)\n", encoding="utf-8")
        written.append(dst)
    return written


def team_init(
    *,
    local_path: str | Path,
    title: str,
    brief: str,
    leader: str,
    leader_capabilities: list[str] | None = None,
    deadline: datetime | None = None,
    remote_url: str | None = None,
) -> dict:
    root = Path(local_path).resolve()
    root.mkdir(parents=True, exist_ok=True)

    repo = GitRepo.init(root, initial_branch="main")

    leader_member = MemberInfo(
        name=leader,
        role=Role.LEADER,
        capabilities=leader_capabilities or [],
    )
    project = ProjectMeta(
        title=title,
        brief=brief,
        deadline=deadline,
        members=[leader_member],
        repo_url=remote_url,
    )

    write_model(_paths.project_json(root), project)
    write_json(
        _paths.members_json(root),
        [leader_member.model_dump(mode="json")],
    )
    write_model(_paths.glossary_json(root), Glossary())

    for d in (
        _paths.tasks_dir(root),
        root / "artifacts",
        root / "reviews",
        root / "final",
    ):
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").write_text("", encoding="utf-8")

    workflow_dir = root / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    (workflow_dir / "teamcollab.yml").write_text(WORKFLOW_YAML, encoding="utf-8")

    script_paths = _copy_runner_scripts(root)

    (root / ".gitignore").write_text(GITIGNORE, encoding="utf-8")

    repo.add(
        [
            _paths.project_json(root),
            _paths.members_json(root),
            _paths.glossary_json(root),
            _paths.tasks_dir(root) / ".gitkeep",
            root / "artifacts" / ".gitkeep",
            root / "reviews" / ".gitkeep",
            root / "final" / ".gitkeep",
            workflow_dir / "teamcollab.yml",
            root / ".gitignore",
            *script_paths,
        ]
    )

    env = EventEnvelope(type=EventType.PROJECT_CREATED, actor=leader)
    sha = repo.commit(env.dump(f"init project {title}"))

    pushed = False
    if remote_url:
        try:
            repo._repo.create_remote("origin", remote_url)
        except Exception:
            pass
        try:
            repo._repo.git.push("-u", "origin", "main")
            pushed = True
        except Exception:
            pushed = False

    return {
        "local_path": str(root),
        "sha": sha,
        "remote_url": remote_url,
        "pushed": pushed,
    }
