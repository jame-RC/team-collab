"""MCP tool implementations. Each tool is a separate module.

Re-exports the public callables so the MCP server entry can do
``from teamcollab.tools import task_list, task_claim, ...`` without
poking at submodules.
"""
from teamcollab.tools.events_recent import events_recent
from teamcollab.tools.glossary import glossary_get, glossary_update
from teamcollab.tools.read_artifact import read_artifact
from teamcollab.tools.search_blackboard import search_blackboard
from teamcollab.tools.sync_now import sync_now
from teamcollab.tools.task_add import task_add
from teamcollab.tools.task_claim import task_claim
from teamcollab.tools.task_create_batch import task_create_batch
from teamcollab.tools.task_list import task_list
from teamcollab.tools.task_review import task_review
from teamcollab.tools.task_submit import task_submit
from teamcollab.tools.team_init import team_init
from teamcollab.tools.team_join import team_join

__all__ = [
    "events_recent",
    "glossary_get",
    "glossary_update",
    "read_artifact",
    "search_blackboard",
    "sync_now",
    "task_add",
    "task_claim",
    "task_create_batch",
    "task_list",
    "task_review",
    "task_submit",
    "team_init",
    "team_join",
]
