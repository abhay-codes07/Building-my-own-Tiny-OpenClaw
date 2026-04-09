"""
Unit tests for context_builder.py
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from context_builder import build_system_prompt, _load_soul
from memory import Memory


class TestLoadSoul:
    def test_returns_string(self):
        result = _load_soul()
        assert isinstance(result, str)
        assert len(result) > 10  # non-trivial content


class TestBuildSystemPrompt:
    def test_includes_skill_names(self):
        skills = [
            {"name": "weather_tool", "description": "Get weather data"},
            {"name": "calculator",   "description": "Do math"},
        ]
        prompt = build_system_prompt(skills)
        assert "weather_tool" in prompt
        assert "calculator"   in prompt
        assert "Get weather data" in prompt

    def test_includes_timestamp(self):
        prompt = build_system_prompt([])
        assert "Current UTC time:" in prompt

    def test_no_skills_still_returns_prompt(self):
        prompt = build_system_prompt([])
        assert isinstance(prompt, str)
        assert len(prompt) > 10

    def test_includes_memory_notes(self, tmp_path):
        mem = Memory(path=str(tmp_path / "m.json"))
        mem.set("note:city", {"content": "Mumbai"})
        mem.set("note:job",  {"content": "engineer"})

        prompt = build_system_prompt([], memory=mem)
        assert "city" in prompt
        assert "Mumbai" in prompt
        assert "job" in prompt
        assert "engineer" in prompt

    def test_non_note_keys_excluded_from_prompt(self, tmp_path):
        mem = Memory(path=str(tmp_path / "m.json"))
        mem.set("internal_flag", "should_not_appear")

        prompt = build_system_prompt([], memory=mem)
        assert "should_not_appear" not in prompt

    def test_empty_memory_no_notes_section(self, tmp_path):
        mem = Memory(path=str(tmp_path / "m.json"))
        prompt = build_system_prompt([], memory=mem)
        assert "What you know about the user" not in prompt
