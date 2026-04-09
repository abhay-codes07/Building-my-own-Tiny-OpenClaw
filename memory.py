"""
memory.py — persistent key-value store for the agent.

All facts the agent saves (via the memory_work skill or any other skill)
live here.  Data is written to MEMORY.json on every mutation so nothing
is lost between restarts.
"""

import json
import os
import time

from logger import get_logger

log = get_logger(__name__)


class Memory:
    """Simple JSON-backed key-value store."""

    def __init__(self, path: str = "MEMORY.json"):
        self.path = path
        self._data: dict = {}

        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self._data = json.load(f)
            log.info("Memory loaded from %s (%d keys)", path, len(self._data))
        else:
            log.info("Fresh memory store — no existing file at %s", path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set(self, key: str, value) -> None:
        """Persist a key-value pair and flush to disk."""
        self._data[key] = value
        self._save()
        log.debug("Memory set: %s", key)

    def get(self, key: str, default=None):
        """Retrieve a stored value, or *default* if the key is missing."""
        return self._data.get(key, default)

    def delete(self, key: str) -> bool:
        """Remove a key.  Returns True if it existed."""
        if key in self._data:
            del self._data[key]
            self._save()
            log.debug("Memory deleted: %s", key)
            return True
        return False

    def keys(self) -> list[str]:
        """Return all stored keys."""
        return list(self._data.keys())

    def all(self) -> dict:
        """Return a shallow copy of the full store (read-only intent)."""
        return dict(self._data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, default=str)
