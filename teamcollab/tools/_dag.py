"""DAG validation + weak-suggestion helpers shared by task_create_batch / task_add.

Hard checks (raise :class:`DagError`):

* ``task_id`` matches the contract pattern and is unique within the batch
* every entry in ``deps`` exists somewhere in (existing tasks ∪ batch)
* the combined graph has no cycle
* every assigned ``owner`` is a known member name

Soft checks (returned as ``warnings`` strings, never raise):

* a single node that >3 tasks all depend on directly (single-root bottleneck)
* an unowned task (orphan)
* an owner with too many in-flight tasks (overload, threshold = 4)

The point of separating hard vs soft: hard failures stop the operation cold,
warnings get surfaced to the coordinator skill so the leader can decide
whether the topology smells right.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable

from teamcollab.contracts import TaskContract


class DagError(ValueError):
    """A structural problem the leader must fix before tasks can be written."""


def validate_and_warn(
    new_tasks: list[TaskContract],
    *,
    existing_tasks: Iterable[TaskContract] = (),
    member_names: Iterable[str] = (),
) -> list[str]:
    """Hard-validate, then return weak-suggestion warnings."""
    existing_list = list(existing_tasks)
    member_set = set(member_names)

    existing_ids = {t.task_id for t in existing_list}
    new_ids = [t.task_id for t in new_tasks]

    dup_in_batch = [tid for tid, n in Counter(new_ids).items() if n > 1]
    if dup_in_batch:
        raise DagError(f"duplicate task_id in batch: {sorted(dup_in_batch)}")

    clashes = sorted(set(new_ids) & existing_ids)
    if clashes:
        raise DagError(f"task_id already exists in repo: {clashes}")

    all_ids = existing_ids | set(new_ids)
    for t in new_tasks:
        missing = [d for d in t.deps if d not in all_ids]
        if missing:
            raise DagError(f"task {t.task_id} has unknown deps: {missing}")
        if t.owner is not None and member_set and t.owner not in member_set:
            raise DagError(
                f"task {t.task_id} owner '{t.owner}' is not in members.json"
            )

    graph: dict[str, list[str]] = defaultdict(list)
    for t in list(existing_list) + list(new_tasks):
        graph[t.task_id] = list(t.deps)

    cycle = _find_cycle(graph)
    if cycle:
        raise DagError(f"cycle detected: {' -> '.join(cycle)}")

    warnings: list[str] = []

    indeg = Counter()
    for t in new_tasks + existing_list:
        for d in t.deps:
            indeg[d] += 1
    for tid, n in indeg.items():
        if n > 3:
            warnings.append(
                f"single-root bottleneck: {n} tasks depend directly on {tid}"
            )

    for t in new_tasks:
        if t.owner is None:
            warnings.append(f"orphan task: {t.task_id} has no owner")

    owner_load: Counter[str] = Counter()
    for t in list(existing_list) + list(new_tasks):
        if t.owner:
            owner_load[t.owner] += 1
    for owner, load in owner_load.items():
        if load > 4:
            warnings.append(f"owner overload: {owner} has {load} tasks")

    return warnings


def _find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in graph}
    parent: dict[str, str | None] = {n: None for n in graph}

    def dfs(start: str) -> list[str] | None:
        stack = [(start, iter(graph.get(start, [])))]
        color[start] = GRAY
        while stack:
            node, it = stack[-1]
            try:
                nxt = next(it)
            except StopIteration:
                color[node] = BLACK
                stack.pop()
                continue
            if nxt not in color:
                color[nxt] = WHITE
                parent[nxt] = node
            if color[nxt] == GRAY:
                cycle = [nxt, node]
                cur = parent.get(node)
                while cur is not None and cur != nxt:
                    cycle.append(cur)
                    cur = parent.get(cur)
                cycle.append(nxt)
                cycle.reverse()
                return cycle
            if color[nxt] == WHITE:
                color[nxt] = GRAY
                parent[nxt] = node
                stack.append((nxt, iter(graph.get(nxt, []))))
        return None

    for n in list(graph):
        if color.get(n, WHITE) == WHITE:
            color[n] = GRAY
            res = dfs(n)
            if res:
                return res
    return None
