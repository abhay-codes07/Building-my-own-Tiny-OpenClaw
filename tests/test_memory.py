"""
Unit tests for memory.py

Runs without touching the real MEMORY.json — uses a temp file.
"""

import json
import os
import tempfile

import pytest

# Adjust path so tests can import the project root modules
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from memory import Memory


@pytest.fixture()
def tmp_memory(tmp_path):
    """Provide a Memory instance backed by a temporary file."""
    mem_file = tmp_path / "TEST_MEMORY.json"
    return Memory(path=str(mem_file))


class TestMemoryBasics:
    def test_set_and_get(self, tmp_memory):
        tmp_memory.set("name", "Alice")
        assert tmp_memory.get("name") == "Alice"

    def test_get_missing_returns_default(self, tmp_memory):
        assert tmp_memory.get("nonexistent") is None
        assert tmp_memory.get("nonexistent", "fallback") == "fallback"

    def test_keys_empty_initially(self, tmp_memory):
        assert tmp_memory.keys() == []

    def test_keys_after_set(self, tmp_memory):
        tmp_memory.set("a", 1)
        tmp_memory.set("b", 2)
        assert set(tmp_memory.keys()) == {"a", "b"}

    def test_delete_existing_key(self, tmp_memory):
        tmp_memory.set("x", 42)
        result = tmp_memory.delete("x")
        assert result is True
        assert tmp_memory.get("x") is None

    def test_delete_missing_key_returns_false(self, tmp_memory):
        assert tmp_memory.delete("no_such_key") is False

    def test_all_returns_copy(self, tmp_memory):
        tmp_memory.set("foo", "bar")
        snapshot = tmp_memory.all()
        snapshot["foo"] = "modified"          # mutate the copy
        assert tmp_memory.get("foo") == "bar"  # original unchanged


class TestMemoryPersistence:
    def test_data_persists_across_instances(self, tmp_path):
        path = str(tmp_path / "persist.json")
        m1 = Memory(path=path)
        m1.set("city", "Bengaluru")

        m2 = Memory(path=path)
        assert m2.get("city") == "Bengaluru"

    def test_file_is_valid_json(self, tmp_path):
        path = str(tmp_path / "valid.json")
        m = Memory(path=path)
        m.set("key", {"nested": True})

        with open(path) as f:
            data = json.load(f)

        assert data["key"] == {"nested": True}

    def test_overwrite_existing_key(self, tmp_memory):
        tmp_memory.set("mood", "happy")
        tmp_memory.set("mood", "ecstatic")
        assert tmp_memory.get("mood") == "ecstatic"
