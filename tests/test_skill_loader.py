"""
Unit tests for skill_loader.py

Uses a temporary skills directory so we don't depend on the real skills/.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from skill_loader import SkillLoader


def _write_skill(skills_root, folder_name, name, description, tool_name):
    """Helper: create a minimal valid skill in a temp directory."""
    skill_dir = os.path.join(skills_root, folder_name)
    os.makedirs(skill_dir, exist_ok=True)

    with open(os.path.join(skill_dir, "SKILL.md"), "w") as f:
        f.write(f"---\nname: {name}\ndescription: {description}\n---\n")

    with open(os.path.join(skill_dir, "handler.py"), "w") as f:
        f.write(f"""\
tools = [{{
    "name": "{tool_name}",
    "description": "{description}",
    "parameters": {{"type": "object", "properties": {{}}, "required": []}},
}}]

async def execute(tool_name, tool_input, context):
    if tool_name == "{tool_name}":
        return {{"ok": True}}
    return {{"error": "Unknown"}}
""")


@pytest.fixture()
def tmp_skills(tmp_path):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    return str(skills_root)


class TestSkillLoaderLoading:
    def test_loads_valid_skill(self, tmp_skills):
        _write_skill(tmp_skills, "alpha", "alpha", "Does alpha things", "do_alpha")
        sl = SkillLoader()
        sl.load_from_directory(tmp_skills)
        assert any(s["name"] == "alpha" for s in sl.get_active_skills())

    def test_skips_directory_without_skill_md(self, tmp_skills):
        bad_dir = os.path.join(tmp_skills, "bad_skill")
        os.makedirs(bad_dir)
        with open(os.path.join(bad_dir, "handler.py"), "w") as f:
            f.write("tools = []\n")
        sl = SkillLoader()
        sl.load_from_directory(tmp_skills)
        assert sl.get_active_skills() == []

    def test_loads_multiple_skills(self, tmp_skills):
        _write_skill(tmp_skills, "s1", "skill_one", "One", "tool_one")
        _write_skill(tmp_skills, "s2", "skill_two", "Two", "tool_two")
        sl = SkillLoader()
        sl.load_from_directory(tmp_skills)
        names = {s["name"] for s in sl.get_active_skills()}
        assert names == {"skill_one", "skill_two"}

    def test_no_skills_dir_is_safe(self, tmp_path):
        sl = SkillLoader()
        sl.load_from_directory(str(tmp_path / "nonexistent"))
        assert sl.get_tools() == []


class TestSkillLoaderTools:
    def test_get_tools_returns_all_tools(self, tmp_skills):
        _write_skill(tmp_skills, "t1", "t1", "T1", "tool_a")
        _write_skill(tmp_skills, "t2", "t2", "T2", "tool_b")
        sl = SkillLoader()
        sl.load_from_directory(tmp_skills)
        tool_names = {t["name"] for t in sl.get_tools()}
        assert tool_names == {"tool_a", "tool_b"}


@pytest.mark.asyncio
class TestSkillLoaderDispatch:
    async def test_execute_known_tool(self, tmp_skills):
        _write_skill(tmp_skills, "my_skill", "my_skill", "desc", "my_tool")
        sl = SkillLoader()
        sl.load_from_directory(tmp_skills)
        result = await sl.execute_tool("my_tool", {}, {"memory": None, "session_id": "x"})
        assert result == {"ok": True}

    async def test_execute_unknown_tool_returns_error(self, tmp_skills):
        sl = SkillLoader()
        sl.load_from_directory(tmp_skills)
        result = await sl.execute_tool("ghost_tool", {}, {})
        assert "error" in result
