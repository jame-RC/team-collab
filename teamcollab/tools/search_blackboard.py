"""``search_blackboard``: keyword-first search across the local clone.

Primary path is ``git grep`` — fast, respects ``.gitignore``, no extra deps.
Optional fallback to fastembed-based semantic search if the caller passes
``semantic=True`` AND fastembed is importable. We never fail the search just
because fastembed isn't installed; we silently degrade to grep-only.

Returns a list of hits, each ``{path, line, snippet}``. Top-k truncation is
applied AFTER both backends so callers always get a stable shape.
"""
from __future__ import annotations

from pathlib import Path

from teamcollab.git_ops import GitRepo


def _grep_hits(repo: GitRepo, query: str, top_k: int) -> list[dict]:
    """Run ``git grep -n -I`` and parse ``path:line:snippet`` output."""
    try:
        # -n line numbers, -I skip binary, -F treat as fixed string for safety,
        # --no-color so the output stays parseable, -e to allow leading dashes.
        raw = repo._repo.git.grep("-n", "-I", "-F", "--no-color", "-e", query)
    except Exception:
        # Either git isn't usable or no matches (git grep exits non-zero on
        # zero matches). Either way: empty result.
        return []

    hits: list[dict] = []
    for line in raw.splitlines():
        # Format: path:line:snippet  (paths are POSIX-style from git)
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        path, lineno, snippet = parts
        hits.append({"path": path, "line": int(lineno), "snippet": snippet.strip()})
        if len(hits) >= top_k:
            break
    return hits


def _semantic_hits(root: Path, query: str, top_k: int) -> list[dict]:
    """Best-effort fastembed search across markdown/json text files.

    Quietly returns ``[]`` if fastembed isn't installed or any error occurs —
    we never want a missing optional dep to break the keyword path.
    """
    try:
        from fastembed import TextEmbedding  # type: ignore
    except Exception:
        return []

    try:
        model = TextEmbedding()
        docs: list[tuple[Path, str]] = []
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix not in (".md", ".json", ".txt"):
                continue
            if ".git" in p.parts:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            docs.append((p, text))

        if not docs:
            return []

        texts = [t for _, t in docs]
        doc_embs = list(model.embed(texts))
        q_emb = next(model.embed([query]))

        # Cosine similarity without numpy.
        def _cos(a, b) -> float:
            num = sum(x * y for x, y in zip(a, b))
            da = sum(x * x for x in a) ** 0.5
            db = sum(y * y for y in b) ** 0.5
            return num / (da * db) if da and db else 0.0

        scored = [
            (_cos(q_emb, doc_embs[i]), docs[i][0], docs[i][1])
            for i in range(len(docs))
        ]
        scored.sort(key=lambda x: x[0], reverse=True)

        out: list[dict] = []
        for score, p, text in scored[:top_k]:
            head = text.strip().splitlines()[:1]
            snippet = head[0] if head else ""
            out.append(
                {
                    "path": p.relative_to(root).as_posix(),
                    "line": 1,
                    "snippet": snippet[:200],
                    "score": round(float(score), 4),
                }
            )
        return out
    except Exception:
        return []


def search_blackboard(
    *,
    local_path: str | Path,
    query: str,
    top_k: int = 10,
    semantic: bool = False,
) -> dict:
    root = Path(local_path).resolve()
    repo = GitRepo(root)

    grep = _grep_hits(repo, query, top_k)
    sem: list[dict] = []
    if semantic:
        sem = _semantic_hits(root, query, top_k)

    return {
        "query": query,
        "grep_hits": grep,
        "semantic_hits": sem,
        "count": len(grep) + len(sem),
    }
