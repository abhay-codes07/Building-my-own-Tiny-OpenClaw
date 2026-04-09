"""
skill_loader.py — discovers and loads skill plugins at startup.

Each skill lives in its own subdirectory under skills/ and must contain:
  SKILL.md   — YAML front-matter with `name:` and `description:`
  handler.py — defines `tools` (list) and async `execute(name, input, ctx)`

Skills are loaded once at startup via load_from_directory().  The loader
then exposes:
  get_active_skills() → list of {name, description} for the system prompt
  get_tools()         → flat list of all tool schemas (sent to the LLM)
  execute_tool()      → dispatches a tool call to the owning skill
"""

import importlib.util
import os

from logger import get_logger

log = get_logger(__name__)


class SkillLoader:
    """Discovers, loads, and dispatches skill plugins."""

    def __init__(self):
        self._skills: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_from_directory(self, skills_dir: str) -> None:
        """Scan *skills_dir* and load every valid skill sub-folder."""
        if not os.path.isdir(skills_dir):
            log.warning("Skills directory not found: %s", skills_dir)
            return

        for entry in sorted(os.listdir(skills_dir)):
            skill_dir = os.path.join(skills_dir, entry)
            if not os.path.isdir(skill_dir):
                continue

            skill_md  = os.path.join(skill_dir, "SKILL.md")
            handler_py = os.path.join(skill_dir, "handler.py")

            if not (os.path.exists(skill_md) and os.path.exists(handler_py)):
                log.debug("Skipping %s — missing SKILL.md or handler.py", entry)
                continue

            try:
                with open(skill_md, encoding="utf-8") as f:
                    name, description = self._parse_skill_md(f.read())

                module = self._import_handler(entry, handler_py)

                self._skills[name] = {
                    "name":        name,
                    "description": description,
                    "tools":       getattr(module, "tools", []),
                    "execute":     getattr(module, "execute", None),
                }
                log.info("Skill loaded: %-20s (%d tool(s))", name, len(self._skills[name]["tools"]))

            except Exception as exc:  # noqa: BLE001
                log.error("Failed to load skill '%s': %s", entry, exc)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_active_skills(self) -> list[dict]:
        """Return [{name, description}] for each loaded skill."""
        return [
            {"name": s["name"], "description": s["description"]}
            for s in self._skills.values()
        ]

    def get_tools(self) -> list[dict]:
        """Return the flat list of all tool schemas from every skill."""
        tools: list[dict] = []
        for skill in self._skills.values():
            tools.extend(skill["tools"])
        return tools

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def execute_tool(self, tool_name: str, tool_input: dict, context: dict):
        """Find the skill that owns *tool_name* and run it."""
        for skill in self._skills.values():
            if any(t["name"] == tool_name for t in skill["tools"]):
                if skill["execute"]:
                    log.debug("Executing tool '%s' via skill '%s'", tool_name, skill["name"])
                    return await skill["execute"](tool_name, tool_input, context)
                return {"error": f"Skill '{skill['name']}' has no execute() function"}

        log.warning("Unknown tool requested: %s", tool_name)
        return {"error": f"Unknown tool: {tool_name}"}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _import_handler(entry: str, handler_py: str):
        spec   = importlib.util.spec_from_file_location(f"skill_{entry}", handler_py)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _parse_skill_md(content: str) -> tuple[str, str]:
        """Extract name and description from SKILL.md front-matter."""
        name = description = ""
        for line in content.splitlines():
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("description:"):
                description = line.split(":", 1)[1].strip()
        if not name:
            raise ValueError("SKILL.md is missing a 'name:' field")
        return name, description
