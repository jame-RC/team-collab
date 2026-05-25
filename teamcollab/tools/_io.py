"""JSON read/write helpers backed by Pydantic.

Tools never call ``json.loads`` / ``json.dumps`` directly. They go through
``read_model`` / ``write_model`` so:

* Schema is enforced on both directions of the disk boundary.
* The on-disk format is stable: 2-space indent, sorted keys, trailing newline.
  This makes git diffs minimal and predictable.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def read_model(path: Path, model: Type[T]) -> T:
    """Parse ``path`` as JSON into the given Pydantic model. Raises if missing or invalid."""
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    return model.model_validate(data)


def read_model_or_default(path: Path, model: Type[T], default: T) -> T:
    if not path.exists():
        return default
    return read_model(path, model)


def write_model(path: Path, instance: BaseModel) -> None:
    """Serialize ``instance`` to JSON and write it atomically to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = instance.model_dump_json(indent=2)
    # Re-parse → re-dump with sorted keys for deterministic on-disk ordering.
    data = json.loads(text)
    text = json.dumps(data, indent=2, sort_keys=True, default=str, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    """Write a plain Python object as JSON (sorted keys, 2-space indent)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True, default=str, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))
